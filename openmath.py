import base64
import math
import re

class OMElement:
	"""An open math object is a tree with some extra data attached.
	Each element may have a number of leaves, which should really be other OpenMath objects. """
	
	_attrib   = None
	_children = None
	tag_name = NotImplemented #should be provided by subclasses
	
	def __init__(self, **kwargs):
		self._children = []
		if kwargs is None:
			self._attrib = {}
		else:
			self._attrib = kwargs
	
	#Methods for accessing the children
	def __len__(self):
		return self._children.__len__()
	
	def __iter__(self):
		return self._children.__iter__()
	
	def write_xml(self, write, indent=0):
		#todo: handle comments and PIs
		write('\t'*indentation + self._tag_xml())
		self._write_contents(write, indent)
		write('\n')
		if len(self) > 0:
			write('</OM' + self.tag_name + '>\n')
	
	def _write_contents(self, write, indent):
		for child in self:
			write('\n')
			child.write_xml(write, indent = indent + 1)
	
	def _tag_xml(self):
		out = '<OM' + self.tag_name
		for key in sorted(self._attrib):
			out += ' {}="{}"'.format(
			  key, escape_value(self._attrib[key]))
		if len(self) == 0:
			out += ' />'
		else:
			out += '>'
		return out
	
	def __str__(self):
		out = self._tag_xml()
		if len(self) != 0:
			out += '...{} child(ren)...'
			out += '</OM' + self.tag_name + '>'
		return out

def escape_value(value):
	#todo: ensure that value can be put into the attribute values like name="blah\"\\hello\\\""
	return value

class OMObject(OMElement):
	tag_name = "OBJ"
	
	def __init__(self):
		super().__init__(version="2.0")

#Basic objects
class OMBasic(OMElement):
	_payload  = None
	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self._children = tuple() # basic elements don't have children
	
	def _write_contents(self, write, indent):
		#Some basic objects don't have contents to write.
		pass

class OMInteger(OMBasic):
	tag_name = "I"
	def __init__(self, x, **kwargs):
		if not isinstance(x, int):
			raise TypeError('Payload should be an integer, not a {}'.format(
			  type(x).__name__))
		self._payload = x
		super().__init__(**kwargs)
	
	def _write_contents(self, write, indent):
		write(str(self.)payload))

class OMFloat(OMBasic):
	tag_name = "F"
	def __init__(self, x, **kwargs):
		if not isinstance(x, float):
			raise TypeError('Payload should be a float, not a {}'.format(
			  type(x).__name__))
		if math.isnan(x):
			kwargs['dec'] = 'NaN'
		elif math.isinf(x):
			kwargs['dec'] = str(x).upper()
		else:
			kwargs['dec'] = "{:12e}".format(x)
		super().__init__(**kwargs)

class OMString(OMBasic):
	tag_name = "STR"
	def __init__(self, x, **kwargs):
		if not isinstance(x, str):
			raise TypeError('Payload should be a string, not a {}'.format(
			  type(x).__name__))
		self._payload = x
		super().__init__(**kwargs)
	
	def _write_contents(self, write, indent):
		write(escape_string(self._payload))

def escape_string(str):
	return str.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

class OMBytes(OMBasic):
	tag_name = "B"
	def __init__(self, x, **kwargs):
		if not isinstance(x, bytes):
			raise TypeError('Payload should be a bytes instance, not a {}'.format(
			  type(x).__name__))
		self._payload = x
		super().__init__(**kwargs)
	
	def _write_contents(self, write, indent):
		write(base64.b64encode(self._payload).encode(ascii))

class OMSymbol(OMBasic):
	tag_name = "S"
	def __init__(self, name, cd, cdbase=None, **kwargs)
		kwargs['name'] = validate_name(name)
		kwargs['cd']   = validate_name(cd)
		if cdbase is not None:
			kwargs['cdbase'] = cdbase #todo should be a valid URI

name_regexp = re.compile(""""
^         #starts with
\w        #a word character
[\w-.]*       #zero or more word characters (including digits), dashes, fullstops 
$         #end of string
""", re.VERBOSE)
def validate_name(name):
	if name[0] in '0123456789':
		raise ValueError('Names must begin with a letter, not a digit.')
	if name_regexp.match(name) is None
		raise ValueError('Names must begin with a letter. All other characters should be letters, digits, hyphens or fullstops.')
	return name

class OMVariable(OMBasic):
	tag_name = "V"

#Derived objects

class OMDerived(OMElement):
	pass

class OMForeign(OMDerived):
	pass

#Compound objects

class OMCompound(OMElement):
	pass

class OMApplication(OMCompound):
	pass

class OMAttribution(OMCompound):
	pass

class OMBinding(OMCompound):
	pass

class OMError(OMCompound):
	pass

# if __name__ == '__main__':
	# xml = """  <OMOBJ>
    # <OMA>
      # <OMS name="sin" cd="transc1"/>
      # <OMV name="x"/>
    # </OMA>
  # </OMOBJ>"""
	# o = OMObject.from_xml(xml)