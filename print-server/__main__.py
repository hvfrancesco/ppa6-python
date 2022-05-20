# MIT (C) bitrate16 2022

# Requirements:
# $ sudo apt install bluetooth bluez libbluetooth-dev libopenjp2-7
# $ pip3 install Pillow aiohttp aiohttp_middlewares ppa6 python-dateutil

# Run with
# $ python3 -m print-server


import aiohttp
import io
import aiohttp.web
import aiohttp_middlewares
import ppa6
import atexit
import PIL
import sys
import traceback

from dateutil import tz
from datetime import datetime

from . import print_service

# Config
PRINTER_MODEL = ppa6.PrinterType.A6p
PRINTER_MAC   = '00:15:83:15:bc:5f'
SERVER_PORT   = 11001
BREAK_SIZE    = 100
TIMEZONE      = 'Europe/Moscow'


# Globals
service: print_service.PrintService = None
app: aiohttp.web.Application = None


# Utils
def print_break():
	"""
	Simple page break of given size
	"""
	
	def wrap_print_break(p: ppa6.Printer):
		p.printBreak(BREAK_SIZE)
		date = datetime.now(tz.gettz(TIMEZONE)).strftime("%d.%m.%Y %H:%M:%S.%f")
		print(date, 'done', 'BREAK')
	
	service.add_print_handler(wrap_print_break)


# Handlers

async def post_print_ascii(request: aiohttp.web.Request):
	
	# Get request payload
	if not request.body_exists:
		return aiohttp.web.json_response({
			'status': 'error',
			'message': 'missing request body'
		})
	
	# Clear, post and return length
	text = await request.text()
	
	# Additinally process string
	text.replace('\t', '    ')
	ascii_text = ''.join([i for i in text if (31 < ord(i) or ord(i) == 10) and ord(i) < 127]).strip()
	
	if len(ascii_text) == 0:
		return aiohttp.web.json_response({
			'status': 'error',
			'message': 'empty ascii string'
		})
	
	date = datetime.now(tz.gettz(TIMEZONE)).strftime("%d.%m.%Y %H:%M:%S.%f")
	
	# Log
	print(date, '--->', 'ASCII')
	# print(ascii_text)
	
	# Decorate string
	print_text = ascii_text
	if (request.query.get('print_date', None) == 'true') or (request.query.get('print_date', None) == '1'):
		print_text = f'{date}\n{print_text}'
	
	# Get concentration
	try:
		concenttration = min(2, max(0, int(request.query.get('print_concentration', 0))))
	except:
		concenttration = 0
	
	# Submit image printing task
	def wrap_print_ascii(p: ppa6.Printer):
		p.setConcentration(concenttration)
		p.printASCII(ascii_text)
		p.flushASCII()
		print(date, 'done', 'ASCII')
		
	service.add_print_handler(wrap_print_ascii)
	
	if (request.query.get('print_break', None) == 'true') or (request.query.get('print_break', None) == '1'):
		print_break()
	
	return aiohttp.web.json_response({
		'status': 'result',
		'length': len(ascii_text)
	})

async def post_print_image(request: aiohttp.web.Request):
	
	# Get request payload
	if not request.body_exists:
		return aiohttp.web.json_response({
			'status': 'error',
			'message': 'missing request body'
		})
	
	post = post = await request.post()
	image = post.get('image')
	
	if not image:
		return aiohttp.web.json_response({
			'status': 'error',
			'message': 'missing request image'
		})
	
	try:
		img_content = image.file.read()
		buf = io.BytesIO(img_content)
		img = PIL.Image.open(buf)
		
		# Log
		date = datetime.now(tz.gettz(TIMEZONE)).strftime("%d.%m.%Y %H:%M:%S.%f")
		print(date, '--->', 'Image')
		
		if not img:
			return aiohttp.web.json_response({
				'status': 'error',
				'message': 'invalid request image'
			})
		
		# Get concentration
		try:
			concenttration = min(2, max(0, int(request.query.get('print_concentration', 0))))
		except:
			concenttration = 0
		
		# Submit image printing task
		def wrap_print_image(p: ppa6.Printer):
			p.setConcentration(concenttration)
			p.printImage(img)
			print(date, 'done', 'Image')
		
		service.add_print_handler(wrap_print_image)
		
		# Add page break
		if (request.query.get('print_break', None) == 'true') or (request.query.get('print_break', None) == '1'):
			print_break()
		
		# Return size of payload
		return aiohttp.web.json_response({
			'status': 'result',
			'length': len(img_content)
		})
		
	except:
		type, value, _ = sys.exc_info()
		return aiohttp.web.json_response({
			'status': 'error',
			'message': str(value),
			'type': str(type)
		})


def main():
	
	# Init app
	global app
	app = aiohttp.web.Application(middlewares=[
		aiohttp_middlewares.cors_middleware(allow_all=True),
	])
	
	# Init printing service
	global service
	service = print_service.PrintService(60, 1, 5)
	service.start(PRINTER_MAC, PRINTER_MODEL)
	
	# Attach routes
	app.router.add_post('/print_ascii', post_print_ascii)
	app.router.add_post('/print_image', post_print_image)
	
	# Register exit handler
	atexit.register(dispose)
	
	# Run
	aiohttp.web.run_app(app, port=SERVER_PORT)

def dispose():
	service.stop()

if __name__ == '__main__':
	main()
