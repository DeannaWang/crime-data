# crime-data
NSW Crime Data Import and Publication Service (Assignment2 of COMP9321 18s1)

Installation Guide

Server
- Unzip server.zip
- Open folder server as a project in PyCharm
- Create a virtual env for the project using Python 3.6 as Base interpreter
- run in Terminal: \[env_folder_path\]/bin/pip install -r \[server_folder_path\]/requirements.txt
- Run app/main.py to start the service
- Supports basic CORS

Client
- Run the server
- Unzip client.zip
- Open client.html in client folder with a web browser
- Already tested with Safari, Chrome and Firefox on Mac OS

Files in server:
- app
	- main.py
	- Tools.py
	- DataBase.py
- data
	- post_code.csv
- requirements.txt

Files in client:
- client.html
