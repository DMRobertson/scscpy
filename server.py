import asyncio
import logging
import os
import re

from xml.etree.ElementTree import _escape_attrib, TreeBuilder
from xml.parsers.expat     import ParserCreate

#We begin with the code which starts the server and closes it on KeyboardInterrupt
def main():
	loop = asyncio.get_event_loop()
	coro = asyncio.start_server(connection_callback, '127.0.0.1', 26133)
	server = loop.run_until_complete(coro)
	logger.info('Looking for SCSCP connections on {}'.format(
	  server.sockets[0].getsockname()))
	
	#Serve requests until CTRL+c is pressed
	logger.info("Press Control-C to stop the server.")
	try:
		loop.run_until_complete(do_nothing())
	except KeyboardInterrupt:
		logger.info("Closing the server.")
	finally:
		server.close()
		loop.run_until_complete(server.wait_closed())
		loop.close()

def connection_callback(reader, writer):
	SCSCPService(reader, writer)

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
	logger.setLevel(logging.DEBUG)
	
	console = logging.StreamHandler()
	console.setLevel(logging.INFO)
	formatter = logging.Formatter('%(levelname)-8s %(name)-27s %(message)s')
	console.setFormatter(formatter)
	logger.addHandler(console)
	
	filename = 'logs/{}.log'.format(name)
	os.makedirs(os.path.dirname(filename), exist_ok=True)
	file = logging.FileHandler(filename, mode='wt', encoding='UTF-8')
	file.setLevel(logging.DEBUG)
	formatter = logging.Formatter('[%(asctime)s] %(levelname)-8s %(message)s')
	file.setFormatter(formatter)
	logger.addHandler(file)
	
	return logger

logger = setup_logging('scscp server')
setup_logging('asyncio')

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
	
	def __init__(self, reader, writer):
		"""The functions in :func:`main` which we imported from :mod:`py3:asyncio` ensure that an instance of this class is created whenever a connection is established. The arguments are :class:`py3:asyncio.StreamReader` and :class:`py3:asyncio.StreamWriter` instances, which handle boring things like buffering.
		"""
		self._reader = reader
		self._writer = writer
		# self._parser = ParserCreate()
		ip, port = self._reader._transport.get_extra_info("peername")
		self.client_name = ip + ":" + str(port)
		self.logger = setup_logging("scscp " + self.client_name.replace(":", "-"))
		# self.parser.ProcessingInstructionHandler = self.instruction_received
		
		self.logger.info("Connection established.")
		self.negotiate_version()
	
	def negotiate_version(self):
		negotiated = False
		self.send_instruction(
		  'service_name',    self.service_name,
		  'service_version', self.service_version,
		  'service_id',      os.getpid(),
		  'scscp_versions',  "1.3")
		line = yield from self._reader.readline()
		self.logger.info(line)
		key, attrs = self.next_instruction()
		if key == 'quit':
			pass #get rid of this object
		elif 'version' in attrs:
			client_versions = attrs['version'].split()
			if "1.3" in client_versions:
				self.send_instruction("version", "1.3")
				negotiated = True
				self.logging.info("Version negotiation complete")
				#proceed into the main loop
			else:
				self.logger.warning("Client asked for unsupported versions " + client_versions)
				self.send_message("quit", "reason", "not supported version")
				#close the connection
		
		if negotiated:
			pass #start waiting for instructions
	
	def send_instruction(self, *args):
		msg = instruction(*args)
		self._writer.write(msg.encode('UTF-8'))
		self.logger.debug("Sent instruction: {!r}".format(msg))
	
	def next_instruction(self):
		line = ""
		while not line.startswith("<?"):
			line = yield from self._reader.readline()
			if not line:
				raise Exception #todo: connection was closed?
			line = line.decode('UTF-8').rstrip()
		
		return self.instruction_details(line)
	
	def instruction_details(self, line):
		chunks = find_attrs.match(line).groups()
		self.logger.debug('chunks:' + repr(chunks))
		if len(chunks) % 2 == 1:
			key = chunks[0]
			start = 1
		else:
			key = None
			start = 0
		attrs = {}
		for i in range(start, len(chunks), 2):
			attr, value = chunks[i], chunks[i+1]
			if attr is None:
				break
			attrs[attr] = value
		return key, attrs

find_attrs = re.compile("""
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
	main()