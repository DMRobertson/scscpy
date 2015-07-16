import logging
import os

from io import StringIO, BytesIO
from xml.etree.ElementTree import ElementTree

def setup_logging(name):
	"""My preferred setup for logging.
	Levels INFO and higher are printed to stdout (the console).
	Levels DEBUG and higher are written to a log file."""
	logger = logging.getLogger(name)
	logger.setLevel(logging.DEBUG)
	
	console = logging.StreamHandler()
	console.setLevel(logging.INFO)
	# console.setLevel(logging.DEBUG)
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

def indent(elem, level=0):
	"""From http://stackoverflow.com/a/4590052
	In turn this is from http://effbot.org/zone/element-lib.htm#prettyprint
	Adds extra whitespace around tags which is preserved for 
	"""
	i = "\n" + level*"  "
	if len(elem):
		if not elem.text or not elem.text.strip():
			elem.text = i + "  "
		if not elem.tail or not elem.tail.strip():
			elem.tail = i
		for elem in elem:
			indent(elem, level+1)
		if not elem.tail or not elem.tail.strip():
			elem.tail = i
	else:
		if level and (not elem.tail or not elem.tail.strip()):
			elem.tail = i

def pretty_xml_str(element):
	out = StringIO()
	indent(element)
	ElementTree(element).write(out, encoding="unicode")
	return out.getvalue()