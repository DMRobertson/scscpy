import logging
import os

from io import StringIO, BytesIO
from xml.etree.ElementTree import ElementTree

def setup_logging(name):
	"""My preferred setup for logging.
	Levels INFO and higher are printed to stdout (the console).
	Levels DEBUG and higher are written to a log file."""
	logger = logging.getLogger(name)
	logger.setLevel(logging.INFO)
	
	console = logging.StreamHandler()
	console.setLevel(logging.DEBUG)
	formatter = logging.Formatter('%(levelname)-8s %(name)-27s %(message)s')
	console.setFormatter(formatter)
	logger.addHandler(console)
	
	filename = 'logs/{}.log'.format(name.replace(':', '-'))
	os.makedirs(os.path.dirname(filename), exist_ok=True)
	file = logging.FileHandler(filename, mode='at', encoding='UTF-8')
	file.setLevel(logging.DEBUG)
	formatter = logging.Formatter('[%(asctime)s] %(levelname)-8s %(message)s')
	file.setFormatter(formatter)
	logger.addHandler(file)
	
	return logger

def xml_to_str(element):
	#would be nice to have this for debugging
	out = BytesIO()
	ElementTree(element).write(out)
	return out.getvalue().decode()