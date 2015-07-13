class SCSCPError(Exception):
	pass

class NegotiationError(SCSCPError):
	pass

class ClientClosedError(SCSCPError):
	pass