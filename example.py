from scscpy import SCSCPService

class ExampleService(SCSCPService):
	"""An example of how to provide our own services. I need to decide how to handle procedure calls."""
	service_name    = "example service"
	service_version = "0.0.1"

if __name__ == "__main__":
	from scscpy import launch_server;
	launch_server(ExampleService)