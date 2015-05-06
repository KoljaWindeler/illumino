import socket,os,time,json,base64
import hashlib,select,trigger,uuid
import sys,light
from binascii import unhexlify, hexlify
from login import *

MAX_MSG_SIZE = 512000
SERVER_IP = "192.168.1.80"
SERVER_PORT = 9875
mid=str(uuid.getnode())
SERVER_TIMEOUT = 5

# login
l=login()
pw=l.pw
msg_out_ts=0
logged_in=0
file_uploading=""
msg_q=[]
file_q=[]
file_str_q=[]
client_socket=""
last_transfer=time.time()
light_dimming_q=[]
my_state=-1

#******************************************************#
def trigger_handle(event,data):
	global msg_q
	global my_state
	global trigger

	if(event=="uploading"):
		#avoi overloading
		if(len(file_q)<5):
			file_q.append(data)			
	elif(event=="state_change"):
		msg={}
		msg["cmd"]=event
		msg["state"]=data
		msg["detection"]=trigger.detection
		my_state=data
		msg_q.append(msg)
		
		# light dimming stuff
		if(data==3): # deactive and motion
			#light_dimming_q.append((time.time()+0.0,100,0,0,500)) # 4 sec to dimm to warm orange - now
			#light_dimming_q.append((time.time()+0.5,0,0,0,200)) # 4 sec to dimm to warm orange - now
			#light_dimming_q.append((time.time()+0.7,0,0,100,500)) # 4 sec to dimm to warm orange - now
			#light_dimming_q.append((time.time()+1.2,0,0,0,200)) # 4 sec to dimm to warm orange - now
			#light_dimming_q.append((time.time()+1.3,100,0,0,500)) # 4 sec to dimm to warm orange - now
			#light_dimming_q.append((time.time()+1.9,0,0,0,200)) # 4 sec to dimm to warm orange - now
			#light_dimming_q.append((time.time()+2.1,0,0,100,500)) # 4 sec to dimm to warm orange - now
			#light_dimming_q.append((time.time()+2.6,0,0,0,200)) # 4 sec to dimm to warm orange - now
			#light_dimming_q.append((time.time()+2.8,100,70,2,4000)) # 4 sec to dimm to warm orange - now
			light_dimming_q.append((time.time(),100,70,2,4000)) # 4 sec to dimm to warm orange - now
		elif(data==2): # deactive and no motion
			light_dimming_q.append((time.time()+10*60,0,0,0,4000)) # 4 sec to dimm to off - in 10 min from now
			#light_dimming_q.append((time.time(),0,0,0,4000)) # 4 sec to dimm to off - in 10 min from now
	elif(event=="uploading_str"):
		file_str_q.append(data)

#******************************************************#
def upload_str_file(data):
	global logged_in
	if(logged_in!=1):
		print("We can't upload as we are not logged in")
		return -1
	td=data[1]
	msg={}
	msg["cmd"]="wf"
	msg["data"]=base64.b64encode(data[0]).decode('utf-8')
	msg["sof"]=1
	msg["eof"]=1
	msg["msg_id"]=0
	msg["ack"]=-1
	msg["ts"]=td
	msg["fn"]=""

	if(trigger.TIMING_DEBUG):
		td.append((time.time(),"b64 - gen msg"))

	msg["td"]=td
	msg_q.append(msg)


def upload_file(data):
	#print(str(time.time())+" -> this is upload_file with "+path)
	path=data[0]
	td=data[1]

	global logged_in
	if(logged_in!=1):
		print("We can't upload as we are not logged in")
		return -1
	img = open(path,'rb')
	i=0
	while True:
		strng = img.read(MAX_MSG_SIZE-100)

		if(trigger.TIMING_DEBUG):
			td.append((time.time(),"reading img"))

		if not strng:
			break

		msg={}
		msg["cmd"]="wf"
		msg["fn"]=path
		msg["data"]=base64.b64encode(strng).decode('utf-8')
		msg["sof"]=0
		if(i==0):
			msg["sof"]=1
		msg["eof"]=0
		msg["msg_id"]=i	
		msg["ack"]=0 #-1
		msg["ts"]=td
		if(len(strng)!=(MAX_MSG_SIZE-100)):
			msg["eof"]=1
		#print('sending('+str(i)+') of '+path+'...')

		if(trigger.TIMING_DEBUG):
			td.append((time.time(),"b64 - gen msg"))
		
		msg["td"]=td
		msg_q.append(msg)
		#msg=json.dumps(msg)	
		#client_socket.send(msg.encode("UTF-8"))
		i=i+1
	#print(str(time.time())+' all messages for '+path+' are in buffer.. i guess')
	img.close()
	return 0
	# end of while
#******************************************************#
def connect():
	print("[A "+time.strftime("%H:%M:%S")+"] -> connecting ...")
	c_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	try:
		c_socket.connect((SERVER_IP, SERVER_PORT))
	except:
		print("Could not connect to server")
		print("retrying in 3 sec")
		time.sleep(3)
		return -1

	print("[A "+time.strftime("%H:%M:%S")+"] -> connected. Loggin in...")

	#### prelogin
	msg={}
	msg["mid"]=mid
	msg["cmd"]="prelogin"
	msg_q.append(msg)
	#print("sending prelogin request")

	return c_socket

# Main programm
#******************************************************#

trigger.start()
trigger.subscribe_callback(trigger_handle,"")
#trigger.set_interval(10)
#trigger.set_interval(1)

light.start()

comm_wait=0
waiter=[]
hb_out=0
recv_buffer=""

while 1:
	logged_in=0
	client_socket=connect()	
	while(client_socket!=""):
		time.sleep(0.1)
		#************* receiving start ******************#		
		try:
			ready_to_read, ready_to_write, in_error = select.select([client_socket,sys.stdin], [client_socket,], [], 5)
			#print(str(len(ready_to_read))+"/"+str(len(ready_to_write))+"/"+str(len(in_error)))
		except:
			print("select detected a broken connection")
			client_socket=""
			break
	
		# test
		if(len(in_error)>0):
			print("in error!")

		## react on keydown
		if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
			input=sys.stdin.readline()
			if(input[:1]=="q"):
				print("Quit")
				os._exit(1)
			else:
				print("what do you mean by: "+input)
	
		## do some light dimming
		if(len(light_dimming_q) > 0):
			for data in light_dimming_q:
				if(data[0]<=time.time()):
					light_action=data
					light_dimming_q.remove(data)
					if(light_action[1]==-1 and light_action[2]==-1 and light_action[3]==-1):
						light.return_to_old(light_action[4])
					else:
						light.dimm_to(light_action[1],light_action[2],light_action[3],light_action[4])
				
		## react on msg in
		if(len(ready_to_read) > 0):
			#print("one process is ready")
			try:
				data = client_socket.recv(MAX_MSG_SIZE)
				if(len(data)==0):
					print("disconnect")
					client_socket=""
					break;
				data_dec = data.decode("UTF-8")
				#print("Data received:"+str(data))
			except:
				print('client_socket.recv detected error')
				break;
			
			comm_wait=0
			msg_out_ts=0
			data_dec=recv_buffer+data_dec
			data_array=data_dec.split('}')
		
			for a in range(0,len(data_array)-1):
				data_array[a]+='}'

				try:
					enc=json.loads(data_array[a])
				except:
					enc=""
					print("json decode failed on:"+data_array[a])
					break;
			
				if(type(enc) is dict):
					last_transfer=time.time()
					#print("json decoded msg")
					#print(enc)
					if(enc.get("cmd")=="prelogin"):
						#### login 
						#print("received challange "+enc.get("challange"))
						h = hashlib.new('ripemd160')
						h.update(str(pw+enc.get("challange")).encode("UTF-8"))
						#print("total to code="+str(pw+enc.get("challange")))
						pw_c=h.hexdigest()
						#print("result="+pw_c)

						msg={}
						msg["mid"]=mid
						msg["client_pw"]=pw_c
						msg["cmd"]="login"
						msg["state"]=my_state
						msg["ts"]=time.strftime("%d.%m.%Y || %H:%M:%S")
						msg["ack"]=-1
						msg_q.append(msg)
					elif(enc.get("cmd")=="login"):
						if(enc.get("ok")==1):
							logged_in=1
							print("[A "+time.strftime("%H:%M:%S")+"] -> log-in OK")
							print("[A "+time.strftime("%H:%M:%S")+"] setting detection to "+str(enc.get("detection")))
							trigger.set_detection(int(enc.get("detection")))
						else:
							logged_in=0
							print("[A "+time.strftime("%H:%M:%S")+"] -> log-in failed")
					elif(enc.get("cmd")=="hb"):
						hb_out=0
						print("[A "+time.strftime("%H:%M:%S")+"] -> connection OK")
					elif(enc.get("cmd")=="set_detection"):
						print("[A "+time.strftime("%H:%M:%S")+"] setting detection to "+str(enc.get("state")))
						trigger.set_detection(enc.get("state"))
					elif(enc.get("cmd")=="wf"):
						ignore=1
					elif(enc.get("cmd")=="set_interval"):
						print("setting interval to "+str(enc.get("interval",0)))
						trigger.set_interval(enc.get("interval",0))
						if(enc.get("interval",0)>0):
							light_dimming_q.append((time.time(),0,100,0,1000)) # 4 sec to dimm to off - in 10 min from now
						else:
							light_dimming_q.append((time.time(),-1,-1,-1,1000)) # 4 sec to dimm to off - in 10 min from now


					else:
						print("unsopported command:"+enc.get("cmd"))
				#end of "if"
			# end of "for"

			if(data_array[len(data_array)-1]==""):
				#if data contained a full message and ended with closing tag, we a$
				recv_buffer=""
			else:
				# but if we grabbed something like 1.5 messages, we should buffer $
				recv_buffer=data_array[len(data_array)-1]
				#print("using buffer!")
		#************* receiving end ******************#
		
		#************* timeout check start ******************#
		if(time.time()-last_transfer>60 and hb_out==0):
			print("[A "+time.strftime("%H:%M:%S")+"] -> checking connection")
			msg={}
			msg["cmd"]="hb"
			msg_q.append(msg)
			hb_out=1
		#************* timeout check end ******************#

		#************* file preperation start ******************#
		if(len(file_q)>0):
			file=file_q[0]
			file_q.remove(file)
			
			if(trigger.TIMING_DEBUG):
				file[1].append((time.time(),"dequeue"))

			if(upload_file(file)!=0):
				#error
				client_socket=""
				break

		if(len(file_str_q)>0):
			file=file_str_q[0]
			file_str_q.remove(file)
			
			if(trigger.TIMING_DEBUG):
				file[1].append((time.time(),"dequeue"))

			upload_str_file(file)
		#************* file preperation end ******************#

		#************* sending start ******************#
		if(len(msg_q)>5):
			print("msg_q: "+str(msg_q)+", comm wait: "+str(comm_wait)+", logged in: "+str(logged_in))

		if(len(msg_q)>0 and (comm_wait==0 or logged_in!=1)):
			msg=""
			#print("We have "+str(len(msg_q))+" waiting...")
			if(logged_in!=1):
				for msg_i in msg_q:
					if(msg_i["cmd"]=="prelogin"):
						print("[A "+time.strftime("%H:%M:%S")+"] -> requesting challange")
						msg=msg_i
						msg_q.remove(msg_i)
					if(msg_i["cmd"]=="login"):
						print("[A "+time.strftime("%H:%M:%S")+"] -> sending login")
						msg=msg_i
						msg_q.remove(msg_i)
					
			else:
				msg=msg_q[0]
				msg_q.remove(msg)
			
			if(msg!=""):
				#print("A message is ready to send")
				send_msg=json.dumps(msg)
				if(json.loads(send_msg).get("cmd"," ")=="wf"):
					if(json.loads(send_msg).get("sof",0)==1):
						print("[A "+time.strftime("%H:%M:%S")+"] -> uploading "+json.loads(send_msg).get("fn"))
				try:
					client_socket.send(send_msg.encode("UTF-8"))
				except:
					client_socket=""
					print("init reconnect")
					break
				#print("message send")
				if(json.loads(send_msg).get("ack",0)==-1):
					#print("waiting on response")
					comm_wait=1
					msg_out_ts=time.time()
				if(json.loads(send_msg).get("cmd"," ")=="wf"):
					if(json.loads(send_msg).get("eof",0)==1):
						print("[A "+time.strftime("%H:%M:%S")+"] -> uploading "+json.loads(send_msg).get("fn")+" done")
						#print("[A "+time.strftime("%H:%M:%S")+"] -> upload took:"+str(time.time()-file_upload_start))
						if(trigger.TIMING_DEBUG):
							msg["td"].append((time.time(),"upload done"))
							old=msg["td"][0][0]
							for a in msg["td"]:
								print("[A "+time.strftime("%H:%M:%S")+"] -> event:"+a[1]+":"+str(int((a[0]-old)*1000))+"ms")
								old=a[0]
							os._exit(1)


		elif(comm_wait==1 and logged_in==1):
			if(len(msg_q)>0 and msg_out_ts!=0 and msg_out_ts+SERVER_TIMEOUT<time.time()):
				print("[A "+time.strftime("%H:%M:%S")+"] -> server did not send ack")
				comm_wait=0
		#************* sending end ******************#
	print("connection destroyed, reconnecting")		
		
#exit()
