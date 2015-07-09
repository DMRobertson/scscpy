import asyncio
import logging
import os
logging.basicConfig(level=logging.INFO)

class SCSCProtocol(asyncio.Protocol):
	#Connection callbacks
	def connection_made(self, transport):
		...
		peername = transport.get_extra_info('peername')
		logging.info('Connection from {}'.format(peername))
		self.transport = transport
	
	def connection_lost(self, exc):
		logging.info('Lost connection to {}. Exception: {}'.format(
		  self.transport.get_extra_info('peername'), exc))
	
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

def do_nothing():
	#Signals like the KeyboardInterrupt are not supported on windows.
	#This workaround forces the loop to 'check' for keyboard interrupts once a second.
	#See http://bugs.python.org/issue23057
	while True:
		yield from asyncio.sleep(1)

def main():
	loop = asyncio.get_event_loop()	
	coro = loop.create_server(SCSCProtocol, '127.0.0.1', 26133)
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