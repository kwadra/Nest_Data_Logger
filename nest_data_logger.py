#! /usr/bin/env python
#################################################
#			Nest Data Logger					#
#################################################
# Zachary Priddy - 2015 						#
# me@zpriddy.com 								#
#												#
# Features: 									#
#	- Data logging with daily data saved to a 	#
#		pickle file								#
#	- Daily Graph generated using pygal 		#
#################################################
#################################################


#########
#IMPORTS
#########
import argparse
import nest
import utils
import pickle
from datetime import * 
import time
import dateutil.parser
import threading
import pygal
from pygal.style import DarkStyle


#########
#VARS
#########
programName="nest_data_logger.py"
programDescription="This program calls the nest API to record data every two minutes to render a daily graph"


debug = False
away_temp = 0
second_timestamp = ''


##################################################
#FUNCTIONS
##################################################

###########
# GET ARGS
##########
def getArgs():
	parser = argparse.ArgumentParser(prog=programName, description=programDescription)
	parser.add_argument("-u","--username",help="Nest Account Username",required=True)
	parser.add_argument("-p","--password",help="Nest Account Password",required=True)
	#parser.add_argument("-f","--accountfile",help="Nest Account Ifno Saved In File",required=False) #To Add In Later
	parser.add_argument("-d","--debug",help="Debug Mode - One Time Run and Debug Info",required=False,action="store_true")


	return parser.parse_args()

##############
# END OF ARGS
##############


def readUserFromFile(user,filename):
	print "Read Account File"

def nestAuth(user):
	myNest = nest.Nest(user.username,user.password,cache_ttl=0)
	return myNest

def dataLoop(nest):
	global debug
	global second_timestamp
	if(not debug):
		threading.Timer(120,dataLoop,args=[nest]).start()
	print "Running Data Loop..."

	timestamp = round(time.time())
	dayLog = []
	log_filename = 'logs/{}-{}-{}.log'.format(datetime.now().year, datetime.now().month, datetime.now().day)
	try:
		dayLog = pickle.load(open(log_filename, 'rb'))
		dayLogIndex = len(dayLog)
	except:
		print "No Current Log File"
		dayLogIndex = 0 


	log = {}
	data = nest.devices[0]
	structure = nest.structures[0]
	deviceData(data,log)
	sharedData(data, log)
	weatherData(data,log)

	structureData(structure,log)

	log['$timestamp'] = datetime.fromtimestamp(timestamp).isoformat()

	calcTotals(log,dayLog)
	
	f = open("logs/current_temp.log", "w")
	f.write("{} {}".format(log['current_temperature'], log['current_humidity']))
	f.close()

	

	if(dayLogIndex != 0):
		dayLog.append(log)
		#		print "No chnage in timestamp recieved.. No new data logged."
	else:
		dayLog.append(log)

	try:
		pickle.dump(dayLog,open(log_filename,'wb'))
	except:
		print "Error Saving Log"

	#for x in range(0,len(dayLog)):
	#	print dayLog[x]

	generateGraph(dayLog)

def deviceData(data,log):
	global away_temp
	deviceData = data._device
	log['leaf_temp'] = utils.c_to_f(deviceData['leaf_threshold_cool'])
	away_temp = utils.c_to_f(deviceData['away_temperature_high'])
	log['$timestamp'] = datetime.fromtimestamp(deviceData['$timestamp']/1000).isoformat()
	log['current_humidity'] = deviceData['current_humidity']
	

def sharedData(data,log):
	sharedData = data._shared
	log['target_type'] = sharedData['target_temperature_type']
	log['fan_state'] = sharedData['hvac_fan_state']
	log['target_temperature'] = utils.c_to_f(sharedData['target_temperature'])
	log['current_temperature'] = utils.c_to_f(sharedData['current_temperature'])
	log['ac_state'] = sharedData['hvac_ac_state']

def weatherData(data,log):
	weatherData = data.weather._current
	log['outside_temperature'] = weatherData['temp_f']

def structureData(structure,log):
	global second_timestamp
	structureData = structure._structure
	second_timestamp = datetime.fromtimestamp(structureData['$timestamp']/1000).isoformat()
	log['away'] = structureData['away']

def calcTotals(log, dayLog):
	global away_temp
	dayLogLen = len(dayLog)
	if(dayLogLen == 0):
		log['total_run_time'] = 0
		log['total_run_time_home'] = 0
		log['total_run_time_away'] = 0
		log['total_trans_time'] = 0
		log['trans_time'] = False
	else:
		index = dayLogLen - 1 #list(dayLog)[dayLogLen-1]
		if(log['ac_state'] == False and dayLog[index]['ac_state'] == False):
			log['total_run_time'] = dayLog[index]['total_run_time']
			log['total_run_time_home'] = dayLog[index]['total_run_time_home']
			log['total_run_time_away'] = dayLog[index]['total_run_time_away']
			log['trans_time'] = False
			log['total_trans_time'] = dayLog[index]['total_trans_time']
		else:
			then = dateutil.parser.parse(dayLog[index]['$timestamp'])
			now = dateutil.parser.parse(log['$timestamp'])
			diff = now - then
			diff = diff.total_seconds()/60
			log['total_run_time'] = dayLog[index]['total_run_time'] + diff

			if(log['away']):
				print "CURRENTLY AWAY"
				log['total_run_time_away'] = dayLog[index]['total_run_time_away'] + diff
				log['total_run_time_home'] = dayLog[index]['total_run_time_home']
				log['target_temperature'] = away_temp
			elif(not log['away']):
				log['total_run_time_home'] = dayLog[index]['total_run_time_home'] + diff
				log['total_run_time_away'] = dayLog[index]['total_run_time_away']

			if(log['away'] == False and dayLog[index]['away'] == True and log['ac_state'] == True):
				log['trans_time'] = True
				log['total_trans_time'] = dayLog[index]['total_trans_time'] + diff
			elif(log['away'] == False and dayLog[index]['away'] == False and dayLog[index]['trans_time'] == True):
				log['trans_time'] = True
				log['total_trans_time'] = dayLog[index]['total_trans_time'] + diff
			else:
				log['trans_time'] = False
				log['total_trans_time'] = dayLog[index]['total_trans_time']

	if(log['away']):
		print "CURRENTLY AWAY"
		log['target_temperature'] = away_temp




def generateGraph(dayLog):

	timestamps = []
	total_run_time = []
	total_run_time_home = []
	total_run_time_away = []
	total_trans_time = []
	target_temperature = []
	current_temperature = []
	outside_temperature = []

	for log in dayLog:

		# convert back to datetime
		current_timestamp=dateutil.parser.parse(log['$timestamp'])

		timestamps.append(current_timestamp.strftime("%Y-%m-%d %H:%M"))
		total_run_time.append(round(60+log['total_run_time']/20))
		total_run_time_home.append(60+log['total_run_time_home']/20)
		total_run_time_away.append(60+log['total_run_time_away']/20)
		total_trans_time.append(round(log['total_trans_time']))
		target_temperature.append(round(log['target_temperature'],1))
		current_temperature.append(round(log['current_temperature'],1))
		outside_temperature.append(round(log['outside_temperature'],1))

	line_chart = pygal.Line(x_label_rotation=20,
		x_labels_major_every=30,
		show_minor_x_labels=False,
		dots_size=.8,width=1200,
		tooltip_border_radius=2,
		style=DarkStyle)
	line_chart.title = 'Daily Nest Usage'
	line_chart.x_labels = timestamps
	line_chart.add('Total Run Time', total_run_time)
	#line_chart.add('Home Run Time', total_run_time_home)
	#line_chart.add('Away Run Time', total_run_time_away)
	#line_chart.add('Trans Run Time', total_trans_time)
	line_chart.add('Target Temperature', target_temperature)
	line_chart.add('Inside Temperature', current_temperature)
	line_chart.add('Outside Temperature', outside_temperature)

	line_chart.render_to_file('daily.svg')  



#############
# MAIN
#############
def main(args):
	global debug
	if(args.debug):
		debug = True
	nestUser = User(username=args.username,password=args.password) #,filename=args.accountfile)
	myNest = nestAuth(nestUser)

	dataLoop(myNest)



#############
# END OF MAIN
#############

#############
# USER CLASS
#############
class User:
	def __init__(self,username=None,password=None,filename=None):
		self.username = username
		self.password = password
		self.filename = filename

###########################
# PROG DECLARE
###########################
if __name__ == '__main__':
	args = getArgs()
	main(args)


