import asyncio
import logging
import os
logging.basicConfig(level=logging.INFO)

class SCSCProtocol(asyncio.Protocol):
	#To provide a service, subclass and give this data?
	service_name = None
	service_version = None
	
	#SCSCP-specific data
	scscp_versions = "1.3"
	
	#Connection callbacks
	def connection_made(self, transport):
		self.peername = transport.get_extra_info('peername')
		logging.info('Connection from {}'.format(self.peername))
		self.transport = transport
		init_msg = instruction(
		  'service_name',    self.service_name,
		  'service_version', self.service_version,
		  'service_id',      os.getpid(),
		  'scscp_versions',  self.scscp_versions
		)
		transport.write(init_msg.encode('ascii'))
	
	def connection_lost(self, exc):
		logging.info('Lost connection to {}. Exception: {}'.format(
		  self.peername, exc))
	
	#Data streaming callbacks
	def data_received(self, data):
		message = data.decode()
		print('Data received: {!r}'.format(message))
	
		print('Send: {!r}'.format(message))
		self.transport.write(data.upper())
	
		print('Close the client socket')
		self.transport.close()
	
	def eof_received(self):
		...

class DummyService(SCSCProtocol):
	service_name = "dummy"
	service_version = "0.0.1"

def instruction(*args):
	assert len(args) % 2 == 0
	details = ""
	pairs = zip(args[::2], args[1::2])
	for attrib, value in pairs:
		details += "{}=\"{}\" ".format(attrib, et._escape_attrib(str(value)))
	return "<?scscp" + details + "?>"

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
		print("Closing the server.")
	finally:
		server.close()
		#wait until the close method completes
		loop.run_until_complete(server.wait_closed())
		#nothing else is using the event loop so we can safely get rid of it
		loop.close()

if __name__ == "__main__":
	main()