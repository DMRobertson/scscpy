import asyncio
import logging
import os
import re

from enum                  import Enum
from xml.parsers.expat     import ParserCreate
from xml.etree.ElementTree import _escape_attrib

# logging.basicConfig(level=logging.INFO)
logging.basicConfig(level=logging.DEBUG)


class SessionState(Enum):
	negotiation  = 0
	transactions = 1

class SCSCProtocol(asyncio.Protocol):
	#To provide a service, subclass and give this data?
	service_name = None
	service_version = None
	
	#SCSCP-specific data
	scscp_versions = "1.3"
	
	#instance attributes
	peername = None
	transport = None
	state = None
	parser = None
	
	#Connection callbacks
	def connection_made(self, transport):
		self.peername = transport.get_extra_info('peername')
		logging.info('Connection from {}'.format(self.peername))
		self.transport = transport
		self.state = SessionState.negotiation
		self.parser = ParserCreate()
		self.parser.ProcessingInstructionHandler = self.instruction_received
		
		init_msg = instruction(
		  'service_name',    self.service_name,
		  'service_version', self.service_version,
		  'service_id',      os.getpid(),
		  'scscp_versions',  self.scscp_versions
		)
		logging.debug("Begin connection initiation")
		transport.write(init_msg.encode('UTF-8'))
		logging.debug("Sent: {!r}".format(init_msg))
		logging.info("Waiting for client response.")
	
	def connection_lost(self, exc):
		logging.info('Lost connection to {}.')
		if exc is not None:
			logging.info('Exception: {}'.format(self.peername, exc))
	
	#Data streaming callbacks
	def data_received(self, data):
		message = data.decode()
		logging.debug('Received: {!r}'.format(message))
		self.parser.Parse(message)
		
		# print('Send: {!r}'.format(message))
		# self.transport.write(data.upper())
	
		# print('Close the client socket')
		# self.transport.close()
	
	def instruction_received(self, target, data):
		data = data.strip()
		logging.info("Received instruction: {!r}".format(data))
		if target != "scscp":
			raise ValueError #todo: more specific details here
		details = instruction_details(data)
		logging.debug("Instructions parsed: {!r}".format(details))
		
		if 'quit' in details:
			msg = "{} quit".format(self.peername)
			if 'reason' in details:
				msg += ' ({})'.format(details['reason'])
			logging.info(msg)
			self.transport.close()
	
	def eof_received(self):
		...

class AttrState(Enum):
	key = 0
	value = 1

find_attrs = re.compile("""
(?:          #look for something matching
  ([^=\s]+)    #key: non-empty seq of non-space non-equals characters
  (?:          #optionally followed by a single
    ="           #start value
      ([^"]*)      #value: sequence of non-quote chars
    "            #end value
  )?
)""", re.VERBOSE)

def instruction_details(data):
	logging.debug(data)
	attrs = {}
	for match in find_attrs.finditer(data):
		key, value = match.groups()
		attrs[key] = value
	return attrs

def instruction(*args):
	assert len(args) % 2 == 0
	details = ""
	pairs = zip(args[::2], args[1::2])
	for attrib, value in pairs:
		details += "{}=\"{}\" ".format(attrib, _escape_attrib(str(value)))
	return "<?scscp " + details + "?>\n"

def do_nothing():
	#Signals like the KeyboardInterrupt are not supported on windows.
	#This workaround forces the loop to 'check' for keyboard interrupts once a second.
	#See http://bugs.python.org/issue23057
	while True:
		yield from asyncio.sleep(1)




class DummyService(SCSCProtocol):
	service_name = "dummy"
	service_version = "0.0.1"

def main():
	loop = asyncio.get_event_loop()	
	coro = loop.create_server(DummyService, '127.0.0.1', 26133)
	server = loop.run_until_complete(coro)
	logging.info('Looking for SCSCP connections on {}'.format(
	  server.sockets[0].getsockname()))
	
	#Serve requests until CTRL+c is pressed
	print("Press control-C to stop the server.")
	try:
		loop.run_until_complete(do_nothing())
	except KeyboardInterrupt:
		print("Closing the server.")
	finally:
		server.close()
		#wait until the close method completes
		loop.run_until_complete(server.wait_closed())
		#nothing else is using the event loop so we can safely get rid of it
		loop.close()

if __name__ == "__main__":
	main()