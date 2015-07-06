from xml.etree.elementTree import Element

class Element:
	"""An open math object is a tree with some extra data attached.
	Each element may have a number of leaves, which should really be other OpenMath objects. """
	
	tag_name = None
	def __init__(self, **kwargs):
		self.children = []
		if kwargs is None:
			self.attrs = {}
		else:
			self.attrs = kwargs

class OMObject(Element):
	
	tag_name = "OBJ"
	
	def __init__(self):
		super().__init__(self, 'OM' + self.tag_name)
		self.attrs = dict()
		

#Basic objects
class OMBasic(OMObject):
	def get(key, default=None):
		raise NotImplementedError("Basic objects ")

class OMInteger(OMBasic, int):
	pass

class OMFloat(OMBasic, float):
	pass

class OMString(OMBasic, str):
	pass

class OMBytes(OMBasic, str):
	pass

class OMSymbol(OMBasic):
	pass

class OMVariable(OMBasic):
	pass

#Derived objects

class OMDerived(OMObject):
	pass

class OMForeign(OMDerived):
	pass

#Compound objects

class OMCompound(OMObject):
	pass

class OMApplication(OMCompound):
	pass

class OMAttribution(OMCompound):
	pass

class OMBinding(OMCompound):
	pass

class OMError(OMCompound):
	pass