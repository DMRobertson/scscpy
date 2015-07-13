import asyncio
import functools
import os

from .errors  import *
from .service import SCSCPService
from .util    import setup_logging

def launch_server(service_cls = None, ip = '127.0.0.1', port = 26133):
	"""Hosts an SCSCP server accepting connections from the given IP and port."""
	if service_cls is None:
		service_cls = SCSCPService
	callback = functools.partial(connection_made, service_cls)
	
	loop = asyncio.get_event_loop()
	coro = asyncio.start_server(callback, ip, port)
	server = loop.run_until_complete(coro)
	logger.info('Looking for connections on {}'.format(
	  server.sockets[0].getsockname()))
	
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
def connection_made(service_cls, reader, writer):
	ip, port = reader._transport.get_extra_info("peername")
	name = ip + ":" + str(port)
	logger.info("Connection made to " + name)
	instance = service_cls(reader, writer, name)
	try:
		yield from instance.negotiate_version()
	except NegotiationError as e:
		instance.logger.error("Version negotation failed: {}".format(e))
		logger.error("Version negotation with {} failed. {}".format(name, e))
		return
	
	#No error if we get this far
	logger.info("Version negotation with {} succeeded. ".format(name))
	try:
		while True:
			key, attrs = yield from instance.read_instruction()
			yield from instance.handle_instruction(key, attrs)
	except ClientQuitError as e:
		if e.reason is not None:
			instance.logger.info("Client quit: " + e.reason)
			logger.info("Client {} quit: {}".format(name, e.reason))
		else:
			instance.logger.info("Client quit")
			logger.info("Client quit")
	except ConnectionClosedError as e:
		instance.logger.info("Client quit")
		logger.info("Client {} quit: {}".format(name))
	finally:
		logger.info("Closing connection to " + name)
		writer.close()

def do_nothing(seconds=1):
	"""Signals like the KeyboardInterrupt are not supported on windows. This workaround forces the event loop to 'check' for keyboard interrupts once a second. See http://bugs.python.org/issue23057"""
	while True:
		yield from asyncio.sleep(seconds)

logger = setup_logging('scscp server')

if __name__ == "__main__":
	#for testing only
	setup_logging('asyncio')
	launch_server()