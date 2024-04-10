
def variable_is_defined(variable):
	try: 
		variable == variable
	except: 
		print(f"The variable {variable} was not previously defined.")