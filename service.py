import asyncio
import re
import os

from enum import Enum
from xml.etree.ElementTree import _escape_attrib, XMLParser

from .util     import setup_logging, pretty_xml_str
from .openmath import verify_call

class SCSCPService:
	"""This class implements the basics of the SCSCProtocol."""
	#Internal attributes
	_reader = None
	_writer = None
	
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
	
	#Basic IO
	@asyncio.coroutine
	def readline(self, include_newline=False):
		line = yield from self._reader.readline()
		if not line:
			raise ConnectionClosedError
		return line.decode('UTF-8').rstrip()
	
	@asyncio.coroutine
	def read_instruction(self, line=""):
		while not line.startswith("<?"):
			line = yield from self.readline()
		
		self.logger.debug("Received instruction: {!r}".format(line))
		key, attrs = instruction_details(line)
		self.logger.debug("key = {!r}; attrs = {}".format(key, attrs))
		return key, attrs
	
	def send_instruction(self, *args):
		msg = instruction(*args)
		self._writer.write(msg.encode('UTF-8'))
		self.logger.debug("Sent instruction: {!r}".format(msg[:-1]))
	
	def inform_client(self, msg):
		self.send_instruction("info", msg)
	
	def report_error(self, msg):
		self.logger.error(msg)
		self.inform_client(msg)
	
	#Version negotation
	@asyncio.coroutine
	def negotiate_version(self):
		self.logger.debug("Beginning version negotiation.")
		self.send_instruction(
		  'service_name',    self.service_name,
		  'service_version', self.service_version,
		  'service_id',      os.getpid(),
		  'scscp_versions',  "1.3")
		
		key, attrs = yield from self.read_instruction()
		if key == 'quit':
			raise ClientQuitError(attrs)
		
		elif 'version' in attrs:
			client_versions = attrs['version'].split()
			if "1.3" in client_versions:
				self.send_instruction("version", "1.3")
				self.logger.info("Version negotiation succeeded")
			else:
				self.send_instruction("quit", "reason", "not supported version")
				raise NegotiationError("Client asked for unsupported versions " + client_versions)
		
		else:
			self.send_instruction("quit", "reason", "Only quit and version messages are allowed during version negotation")
			raise NegotiationError("Received neither a quit nor version message")
	
	#The transaction handling loop
	@asyncio.coroutine
	def handle_instruction(self, key, attrs):
		if key == "start":
			self.logger.info("Receiving OpenMath object")
			obj = yield from self.read_transaction()
			#I think that obj will be none if the transaction fails
			self.handle_object(obj)
		elif key == "cancel":
			self.logger.error("Cancel instruction given before transaction")
		elif key == "end":
			self.logger.error("End instruction given before transaction")
		elif key == "quit":
			#todo kill any computations that are running
			raise ClientQuitError(attrs)
		elif key == "terminate":
			if 'call_id' not in attrs:
				self.report_error("Terminate instruction missing call_id")
			else:
				... #todo kill the given computation or inform client of error
		elif "info" in attrs:
			self.logger.info("Client says: " + attrs['info'])
		else:
			self.report_error("Unrecognised instruction before transaction: key = {}, attrs = {}".format(key, attrs))
	
	@asyncio.coroutine
	def read_transaction(self):
		parser = XMLParser()
		line = ""
		while not line.startswith('<?'):
			line = yield from self.readline()
			parser.feed(line)
		key, attrs = yield from self.read_instruction(line)
		
		if key == 'cancel':
			self.logger.info('Transaction cancelled')
		elif key == 'end':
			self.logger.info('Transaction complete')
			obj = parser.close()
			self.logger.debug(pretty_xml_str(obj))
			return obj
		elif key == 'start':
			self.report_error("Start instruction given mid-transaction")
		else:
			self.report_error("Unrecognised instruction during transaction: key = {}, attrs = {}".format(key, attrs))
	
	#Interpreting the OpenMath objects
	def handle_object(self, obj):
		#1. Check that obj really does represent an openmath object
		name_symbol, args, = verify_call(obj)
		#2. See if we know what to do with that object
		#3. If so, do it
		...

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

def instruction_details(line):
	chunks = parse_instruction.match(line).groups()
	key = chunks[0] #possibly None
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

#Handling transactions

def verify_call(obj):
	"""The only OM object that the client is allowed to send is a procedure call.
	Everything else in the messages (and CDs) is either an argument to the call or some kind of extra data.
	
	Proceedure calls have the following structure:
	<OMOBJ>
		<OMATTR>
			<!-- call_id and option_return_... are mandatory -->
			<OMATP>
				<OMS cd="scscp1" name="call_id" />
				<OMSTR>call_identifier</OMSTR>
				<OMS cd="scscp1" name="option_runtime" />
				<OMI>runtime_limit_in_milliseconds</OMI>
				<OMS cd="scscp1" name="option_min_memory" />
				<OMI>minimal_memory_required_in_bytes</OMI>
				<OMS cd="scscp1" name="option_max_memory" />
				<OMI>memory_limit_in_bytes</OMI>
				<OMS cd="scscp1" name="option_debuglevel" />
				<OMI>debuglevel_value</OMI>
				<OMS cd="scscp1" name="option_return_object" />
				<OMSTR></OMSTR>
			</OMATP>
			<!-- Attribution pairs finished, now the procedure call -->
			<OMA>
				<OMS cd="scscp1" name="procedure_call" />
				<OMA>
					<OMS cd="..." name="..."/>
					<!-- Argument 1 -->
					<!-- ... -->
					<!-- Argument M -->
				</OMA>
			</OMA>
		</OMATTR>
	</OMOBJ>
	"""
	assert obj.tag == 'OMOBJ'
	attr = obj[0]
	
	assert attr.tag == 'OMATTR'
	pairs, application = *attr
	
	assert application.tag == 'OMA'
	symbol, args = *application
	
	assert symbol.tag == 'OMS'
	assert symbol['cd'] == "scscp1"
	assert symbol['name'] == "procedure_call"
	
	assert args.tag == 'OMA'
	assert len(args) > 0
	name_symbol = args[0]
	
	assert name_symbol.tag == 'OMS'
	assert 'cd'   in name_symbol
	assert 'name' in name_symbol
	
	#2. Now handle the extra information
	assert pairs.tag == 'OMATP'
	assert len(pairs) % 2 == 0
	
	extras = {}
	call_id = None
	return_type = None
	
	for i in range(0, len(pairs), 2):
		symbol = pairs[i]
		assert elem.tag == 'OMS'
		assert symbol['cd'] == "scscp1"
		name = symbol['name']
		extras[name] = pairs[i+1]
		
		if name == 'call_id':
			assert call_id is None
			call_id = 'name[call_id]'
		elif name.startswith('option_return_'):
			assert return_type is None
			return_type = ReturnTypes[name[14:]]
	
	#Some information is mandatory
	assert call_id     is not None
	assert return_type is not None
	
	return name_symbol, args[1:], extras

class ReturnTypes(Enum):
	nothing = 0
	object  = 1
	cookie  = 2



