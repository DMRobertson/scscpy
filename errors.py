class SCSCPError(Exception):
	pass

class NegotiationError(SCSCPError):
	pass

class ConnectionClosedError(SCSCPError):
	pass

class ClientQuitError(SCSCPError):
	def __init__(self, attrs):
		if 'reason' in attrs:
			self.reason = attrs['reason']
		else:
			self.reason = None