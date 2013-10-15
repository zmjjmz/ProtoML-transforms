#!/usr/bin/python
import json
import cPickle as pickle
import sys, os
import numpy as np
#from optparse import OptParse


class sklearn_transform_base:
	def __init__(self, params_file_s):
		""" Initializes the transform. Only takes a relative path to a JSON file that contains all of the system parameters """
		try:
			edfile = open('%s/transforms/error_dict.json' % os.environ['PROTOML'])
		except KeyError:
			print >> sys.stderr, "FATAL: PROTOML Environment variable not set"
			sys.exit(-1)
		self.error_dict = json.load(edfile)
		edfile.close()
		try:
			params_file = open(params_file_s, 'r')
		except IOError as ioe:
			# Not sure if I should raise an error or exit -- feel free to suggest which
			print >> sys.stderr, "Could not open system parameters", ioe
			sys.exit(self.error_dict['CouldNotOpenSystemParams'])

		try:
			self.params = json.load(params_file)
		except ValueError as vae:
			print >> sys.stderr, "Could not decode parameters:", vae
			sys.exit(self.error_dict['CouldNotParseSystemParams'])

		params_file.close()

		relative_name = self.params['module name'].split('.')[-1] # Final module name, e.g. AffinityPropagation or KMeans

		# Importing
		try:
			__import__(self.params['module name'])
		except ImportError as ime:
			print >> sys.stderr, "Could not import %s:" % self.params['module name'], ime
			sys.exit(error_dict['IncorrectPackage'])

		self.model_module = sys.modules[self.params['module name']]

	def read_hyperparams(self):
		""" Reads the input files based on their formats """
		try:
			self.hyperparams_file = open(self.params['hyperparameters file'],'r')
		except IOError as ioe:
			print >> sys.stderr, "Could not open hyper parameters", ioe
			sys.exit(self.error_dict['CouldNotOpenHyperParameters'])

		try:
			self.hyperparams = json.load(self.hyperparams_file)
		except ValueError as vae:
			print >> sys.stderr, "Could not decode hyperparameters:", vae
			sys.exit(self.error_dict['CouldNotParseHyperParams'])

	def read_data(self):
		""" Reads input data file """
		# We need to take the data and turn it into a numpy array
		dataformat = self.params['idatafmt']
		idatax_filen = self.params['idatax']
		idatay_filen = self.params['idatay']
		if dataformat == 'csv':
			try:
				self.idatax = np.loadtxt(idatax_filen,delimiter=',')
				if idatay_filen != None:
					self.idatay = np.loadtxt(idatay_filen,delimiter=',')
				else:
					self.idatay = None
			except IOError as ioe:
				# I would expand the error handling here to handle each case if it makes sense to do so -- but if this is not the error handling approach we're taking I won't put time into it.
				print >> sys.stderr, "Could not open dataset file:", ioe
				sys.exit(error_dict['CouldNotOpenData'])


	def load_model(self):
		""" Loads the model from the imodel field """
		model_filen = self.params['imodel']
		if model_filen == None:
			return False
		modelfmt = self.params['imodelfmt']
		try:
			imodelfile = open(model_filen, 'r')
		except IOError as ioe:
			print >> sys.stderr, "Could not open model file:", ioe
			sys.exit(error_dict['CouldNotOpenModelFile'])

		if modelfmt == 'pickle':
			try:
				self.imodel = pickle.load(imodelfile)
			except pickle.UnpicklingError as upe:
				print >> sys.stderr, "Problem unpickling:", upe
				sys.exit(error_dict['CouldNotParseModelFile'])
		else:
			print >> sys.stderr, "Unsupported model input format"
			sys.exit(error_dict['UnsupportedModelFormat'])

		return True
	
	def generator(self):
		""" Handle generator transform """
		warm_start = self.load_model()
		if warm_start:
			try:
				self.imodel.set_params(**self.hyperparams)
			except TypeError as tpe:
				print >> sys.stderr, "Wrong hyper parameters", tpe
				sys.exit(error_dict['BadHyperParams'])
		else:
			try:
				self.imodel = self.model_module(**params)
			except TypeError as tpe:
				print >> sys.stderr, "Wrong hyper parameters", tpe
				sys.exit(error_dict['BadHyperParams'])

		# TODO: Integrate kwargs for fit functions
		if self.idatay != None: # Supervised
			self.imodel.fit(self.idatax, self.idatay)
		else: #Unsupervised
			self.imodel.fit(self.idatax)
			
	def executor(self):
		""" Handle executor transform """
		if not self.load_model():
			print >> sys.stderr, "Executor cannot create a model, please supply one."
			sys.exit(error_dict['InvalidExecutor'])

		self.odatay = self.imodel.predict(self.idatax)
	
	def write_model(self):
		""" Write the serialized model if one was generated """
		omodel_filen = self.params['omodel']
		if omodel_filen == None:
			return False
		modelfmt = self.params['omodelfmt']
		try:
			omodelfile = open(omodel_filen, 'w')
		except IOError as ioe:
			print >> sys.stderr, "Could not open model file for writing:", ioe
			sys.exit(error_dict['CouldNotOpenModelFile'])

		if modelfmt == 'pickle':
			try:
				pickle.dump(self.omodel, omodelfile)
			except pickle.PicklingError as pke:
				print >> sys.stderr, "Could not pickle the model", pke
				sys.exit(error_dict['CouldNotWriteModelFile'])
		else:
			print >> sys.stderr, "Unsupported model output format"
			sys.exit(error_dict['BadModelFormat'])

	def write_data(self):
		""" Write the predictions, transformed data (if there is any) """
		dataformat = self.params['odatafmt']
		odatax_filen = self.params['odatax']
		odatay_filen = self.params['odatay']

		if dataformat == 'csv':
			if odatax_filen != None:
				try:
					# Note that while 
					np.savetxt(odatax_filen, self.odatax, delimiter=',')
				except IOError as ioe:
					print >> sys.stderr, "Could not save transformed data file:", ioe
					sys.exit(error_dict['CouldNotWriteData'])	
			if odatay_filen != None:
				try:
					np.savetxt(odatay_filen, self.odatay, delimiter=',')
				except IOError as ioe:
					print >> sys.stderr, "Could not save labels file:", ioe
					sys.exit(error_dict['CouldNotWriteData'])

		else:
			print >> sys.stderr, "Unsupported data output format"
			sys.exit(error_dict['BadDataFormat'])

	def cleanup(self):
		""" Primarily just close up whatever files were used """
		for i in self.__dict__:
			if isinstance(self.__dict__[i], file):
				self.__dict__[i].close()

	def run(self):
		self.read_hyperparams()
		self.read_data()
		if self.params['mode'] == 'executor':
			self.executor()
			self.write_data()
		elif self.params['mode'] == 'generator':
			self.generator()
			self.write_model()
		self.cleanup()

		
if __name__ == "__main__": 
	""" This is how this supposed to be run """
	params_file = sys.argv[1]
	transform = sklearn_transform_base(params_file)
	sklearn_transform_base.run()


