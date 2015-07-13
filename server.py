import asyncio
import functools
import logging
import os
import re

from xml.etree.ElementTree import _escape_attrib, TreeBuilder
from xml.parsers.expat     import ParserCreate

from errors import *

#We begin with the code which starts the server and closes it on KeyboardInterrupt
def main(service_cls = None):
	if service_cls is None:
		service_cls = SCSCPService
	callback = functools.partial(connection_made, service_cls)
	
	loop = asyncio.get_event_loop()
	coro = asyncio.start_server(callback, '127.0.0.1', 26133)
	server = loop.run_until_complete(coro)
	logger.info('Looking for SCSCP connections on {}'.format(
	  server.sockets[0].getsockname()))
	
	#Serve requests until CTRL+c is pressed
	try:
		logger.info("Press Control-C to stop the server.")
		loop.run_until_complete(do_nothing())
	except KeyboardInterrupt:
		logger.info("KeyboardInterrupt received: closing the server.")
	finally:
		server.close()
		loop.run_until_complete(server.wait_closed())
		loop.close()

@asyncio.coroutine
def connection_made(service_factory, reader, writer):
	ip, port = reader._transport.get_extra_info("peername")
	name = ip + ":" + str(port)
	logger.info("Connection made to " + name)
	service = service_factory(reader, writer, name)
	try:
		yield from service.negotiate_version()
	except NegotiationError as e:
		logger.error("Version negotation with {} failed. {}".format(name, e))
		return
	
	#No error if we get this far
	logger.info("Version negotation with {} succeeded. ".format(name))
	try:
		yield from service.handle_instructions()
	except SCSCPError as e:
		logger.error("Encountered error with {}. Details: {}".format(name, e))
	finally:
		logger.info("Closing connection to " + name)
		writer.close()

def do_nothing(seconds=1):
	"""Signals like the KeyboardInterrupt are not supported on windows. This workaround forces the event loop to 'check' for keyboard interrupts once a second. See http://bugs.python.org/issue23057"""
	while True:
		yield from asyncio.sleep(seconds)

#Next comes logging!
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
	file = logging.FileHandler(filename, mode='wt', encoding='UTF-8')
	file.setLevel(logging.DEBUG)
	formatter = logging.Formatter('[%(asctime)s] %(levelname)-8s %(message)s')
	file.setFormatter(formatter)
	logger.addHandler(file)
	
	return logger

logger = setup_logging('scscp server')

#Now we actually implement SCSCP
class SCSCPService:
	"""This class implements the basics of the SCSCProtocol."""
	#Attributes: internals
	_reader = None
	_writer = None
	# _parser = None
	
	#Attributes
	logger = None
	client_name = None
	
	#Service-specific attributes (override in a subclass)
	service_name    = None
	service_version = None
	
	def __init__(self, reader, writer, client_name):
		self._reader     = reader
		self._writer     = writer
		self.client_name = client_name
		# self._parser = ParserCreate()
		
		self.logger = setup_logging("scscp " + self.client_name)
		# self.parser.ProcessingInstructionHandler = self.instruction_received
		self.logger.info("Connection established.")
	
	@asyncio.coroutine
	def negotiate_version(self):
		self.logger.debug("Beginning version negotiation.")
		self.send_instruction(
		  'service_name',    self.service_name,
		  'service_version', self.service_version,
		  'service_id',      os.getpid(),
		  'scscp_versions',  "1.3")
		
		key, attrs = yield from self.next_instruction()
		if key == 'quit':
			if 'reason' in attrs:
				msg = "Client quit during negotiation: " + attrs['reason']
			else:
				msg = "Client quit during negotiation."
			ex = NegotiationError(msg)
			self.logger.error(ex)
			raise ex
		
		elif 'version' in attrs:
			client_versions = attrs['version'].split()
			if "1.3" in client_versions:
				self.send_instruction("version", "1.3")
				self.logger.info("Version negotiation succeeded")
			else:
				ex = NegotiationError("Client asked for unsupported versions " + client_versions)
				self.logger.error(ex)
				self.send_instruction("quit", "reason", "not supported version")
				raise ex
		
		else:
			ex = NegotiationError("Received neither a quit nor version message")
			self.logger.error(ex)
			self.send_instruction("quit", "reason", "Only quit and version messages are allowed during version negotation")
			raise ex
	
	def send_instruction(self, *args):
		msg = instruction(*args)
		self._writer.write(msg.encode('UTF-8'))
		self.logger.debug("Sent instruction: {!r}".format(msg[:-1]))
	
	@asyncio.coroutine
	def next_instruction(self):
		line = ""
		while not line.startswith("<?"):
			line = yield from self._reader.readline()
			if not line:
				raise ClientClosedError
			line = line.decode('UTF-8').rstrip()
		
		self.logger.debug("Received instruction: {!r}".format(line))
		key, attrs = instruction_details(line)
		self.logger.debug("Key = {}; attrs = {}".format(key, attrs))
		return key, attrs
	
	@asyncio.coroutine
	def handle_instructions(self):
		...

def instruction_details(line):
	chunks = parse_instruction.match(line).groups()
	key = chunks[0]
	attrs = {}
	for i in range(1, len(chunks), 2):
		attr, value = chunks[i], chunks[i+1]
		if attr is None:
			break
		attrs[attr] = value
	return key, attrs

parse_instruction = re.compile("""
^<\?       #starts with < followed by literal question mark
\s*scscp   #the phrase 'scscp', possibly after some whitespace
\s+        #some whitespace
(?:         #at most one occurance of 
    (\w+)[ ] #an [alphanumerical string (key)], followed by a space
)?
(?:          #any occurances of
  (\w+)      #an [alphanumerical string (attribute)], followed by a space
  ="         #start value
  ([^"]*)    #a [string of non-quote chars (value)]
  "\s?        #end value, followed by a space
)*
""", re.VERBOSE)

def instruction(*args):
	"""Forms an XML processing instruction (as a string) from the arguments. If there is an odd number of arguments, the first is taken to be a key. The rest are attribute/value pairs, in order. If an even number of arguments is given, they are all treated as attribute/value pairs."""
	if len(args) % 2 == 1:
		details = args[0] + " "
		start = 1
	else:
		details = ""
		start = 0
	for i in range(start, len(args), 2):
		attrib, value = args[i], args[i+1]
		details += "{}=\"{}\" ".format(attrib, _escape_attrib(str(value)))
	return "<?scscp " + details + "?>\n"

if __name__ == "__main__":
	#for testing only
	setup_logging('asyncio')
	main()