import asyncio
import logging
import os
import re

from enum                  import Enum
from xml.parsers.expat     import ParserCreate
from xml.etree.ElementTree import _escape_attrib, TreeBuilder

# logging.basicConfig(level=logging.INFO)
# logging.basicConfig(level=logging.DEBUG)

class SessionState(Enum):
	negotiation  = 0
	awaiting_transaction = 1
	reading_transaction  = 2

class SCSCProtocol(asyncio.Protocol):
	#To provide a service, subclass and give this data?
	service_name = None
	service_version = None
	
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
		
		self.send_instruction(
		  'service_name',    self.service_name,
		  'service_version', self.service_version,
		  'service_id',      os.getpid(),
		  'scscp_versions',  "1.3")
	
	def connection_lost(self, exc):
		if exc is None:
			logging.info('Lost connection to {}.'.format(self.peername))
		if exc is not None:
			logging.warning('Lost connection to {} due to {}'.format(self.peername, exc))
	
	#Data streaming callbacks
	def data_received(self, data):
		message = data.decode('UTF-8')
		logging.debug('Received: {!r}'.format(message))
		self.parser.Parse(message)
	
	def instruction_received(self, target, data):
		logging.debug("Received instruction: {!r}".format(data[:-1]))
		if target != "scscp":
			logging.warning("Ignoring processing instruction with target {}".format(
			  target))
			return
		
		key, attrs = instruction_details(data)
		logging.debug("Instructions parsed: key={!r}, attrs={!r}".format(key, attrs))
		
		#first we deal with version negotiation
		if self.state is SessionState.negotiation:
			if not (key == 'quit' or 'version' in attrs):
				logging.warning("Inappropirate instruction during version negotiation")
				self.quit_session(reason="Only quit or version messages are allowed during negotiation")
			
			#We'll handle quit below
			if 'version' in attrs:
				client_versions = attrs['version'].split()
				if "1.3" in client_versions:
					self.send_instruction("version", "1.3")
					self.state = SessionState.awaiting_transaction
					logging.info("Version negotiation complete. Waiting for a transaction or instruction.")
				else:
					logging.warning("Client asked for unsupported versions {}".format(
					  client_versions))
					self.quit_session("not supported version")
		
		else: #We are not negotiating
			if 'version' in attrs:
				logging.warning('Client {} suppled a version outside of negotiation.'.format(
				  self.peername))
				self.quit_session("Version messages are only allowed during negotiation")
		
		#Now we deal with instructions which may be accepted at any time
		if key == 'quit':
			logging.info("Received quit instruction from {}".format(self.peername))
			self.transport.close()
			#todo stop/pause any calculations that are running?
		elif 'info' in attrs:
			logging.info("{} says: {!r}".format(self.peername, attrs['info']));
		elif key == "start":
			if self.state is not SessionState.awaiting_transaction:
				logging.warning("Unexpected start instruction from {}".format(
				  self.peername))
			else:
				self.state = SessionState.reading_transaction
				logging.debug("Reading transaction from {}".format(self.peername))
		elif key == "cancel":
			if self.state is SessionState.reading_transaction:
				logging.info("Transaction cancelled by {}".format(self.peername))
				self.state = SessionState.awaiting_transaction
			else:
				logging.warning("Ignoring unexpected cancel instruction from {}".format(
				  self.peername))
		elif key == "end":
			#parse the OM object that we ought to have received
			logging.info("Transaction received from {}".format(self.peername))
			self.state = SessionState.awaiting_transaction
		elif key == "terminate":
			... #todo
	
	#SCSCP stuff
	def send_instruction(self, *args):
		msg = instruction(*args)
		self.transport.write(msg.encode('UTF-8'))
		logging.debug("Sent instruction: {!r}".format(msg))
	
	def quit_session(self, reason=None):
		if reason is not None:
			self.send_instruction('quit', 'reason', reason)
		else:
			self.send_instruction('quit')
		self.transport.close()
		logging.info("Closed connection to {}".format(self.peername))

#Forming and parsing processing instructions
find_attrs = re.compile("""
(?:          #at most one occurance of 
    (\w+)[ ] #an [alphanumerical string (key)], followed by a space
)?
(?:          #any occurances of
  (\w+)      #an [alphanumerical string (attribute)], followed by a space
  ="         #start value
  ([^"]*)    #a [string of non-quote chars (value)]
  "\s?        #end value, followed by a space
)*
""", re.VERBOSE)

def instruction_details(data):
	chunks = find_attrs.match(data).groups()
	logging.debug('chunks:' + repr(chunks))
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

def instruction(*args):
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

#Implement service as a subclass...somehow!
class DummyService(SCSCProtocol):
	service_name = "dummy"
	service_version = "0.0.1"

def do_nothing():
	#Signals like the KeyboardInterrupt are not supported on windows.
	#This workaround forces the loop to 'check' for keyboard interrupts once a second.
	#See http://bugs.python.org/issue23057
	while True:
		yield from asyncio.sleep(1)

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
		logging.info("Closing the server.")
	finally:
		server.close()
		#wait until the close method completes
		loop.run_until_complete(server.wait_closed())
		#nothing else is using the event loop so we can safely get rid of it
		loop.close()

if __name__ == "__main__":
	main()