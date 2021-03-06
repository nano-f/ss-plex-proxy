import os
import xml.etree.ElementTree as ET

from flask import Flask, redirect, request, jsonify, Response

from pysmoothstreams import Server, Quality, Protocol, Service
from pysmoothstreams.auth import AuthSign
from pysmoothstreams.exceptions import InvalidService
from pysmoothstreams.guide import Guide

app = Flask(__name__, static_url_path='', static_folder='static')
app.config.from_pyfile('ss-plex-proxy.default_settings')
app.config.from_pyfile('ss-plex-proxy.custom_settings')


@app.route('/channels/<int:channel_number>')
@app.route('/auto/v<int:channel_number>')
def get_channel(channel_number):
	url = guide.generate_streams(Server[server], Quality[quality], auth_sign, protocol=Protocol.MPEG)[channel_number - 1][
		'url']
	return redirect(url)


@app.route('/servers')
def list_servers():
	return jsonify({'servers': [e.name for e in Server]})


@app.route('/hdhomerun/discover.json')
def discover():
	data = {
		'FriendlyName': 'ss-plex-proxy',
		'Manufacturer': 'Silicondust',
		'ModelNumber': 'HDTC-2US',
		'FirmwareName': 'hdhomeruntc_atsc',
		'TunerCount': 6,
		'FirmwareVersion': '201906217',
		'DeviceID': 'xyz',
		'DeviceAuth': 'xyz',
		'BaseURL': request.url_root + 'hdhomerun',
		'LineupURL': request.url_root + 'hdhomerun/lineup.json'
	}
	return jsonify(data)


@app.route('/hdhomerun/lineup.json')
def lineup():
	channels = []

	for stream in guide.channels:
		channels.append({'GuideNumber': str(stream['number']),
		                 'GuideName': stream['name'],
		                 'url': request.url_root + "channels/" + str(stream['number'])})

	return jsonify(channels)


@app.route('/hdhomerun/lineup_status.json')
def lineup_status():
	return jsonify({
		'ScanInProgress': 0,
		'ScanPossible': 1,
		'Source': "Cable",
		'SourceList': ['Cable']
	})

# Used to add a 'lcn' subelement to channel elements as Plex does something weird where it concatenates the channel id
#  and channel name to make the channel number. For fog/altepg this is needed for sane channel numbers.
# https://forums.plex.tv/t/xmltv-parsing-channel-id-and-display-name/219305/20
def add_lcn_element(xmltv):
	channel_number = 1

	tree = ET.fromstring(xmltv)
	for element in tree.iter():
		if element.tag == 'channel':
			lcn = ET.SubElement(element, 'lcn')
			lcn.text = str(channel_number)
			channel_number += 1

	return ET.tostring(tree)


@app.route('/guide')
def guide_data():
	epg_data = add_lcn_element(guide.epg_data)
	if app.config['NANOF_LOGOS']: epg_data = replace_logos(epg_data)
	return Response(epg_data.decode(), mimetype='text/xml')


def replace_logos(xmltv):
	tree = ET.fromstring(xmltv)
	for element in tree.iter():
		if element.tag == 'channel':
			channel_name = element.find('display-name').text
			logo_path = 'static/logos/' + channel_name + '.png'

			if os.path.isfile(logo_path):
				element.find('icon').attrib['src'] = request.url_root + 'logos/' + channel_name + '.png'

	return ET.tostring(tree)


if __name__ == '__main__':
	if app.config['SERVICE'] == "live247":
		service = Service.LIVE247
	elif app.config['SERVICE'] == "starstreams":
		service = Service.STARSTREAMS
	elif app.config['SERVICE'] == "streamtvnow":
		service = Service.STREAMTVNOW
	elif app.config['SERVICE'] == "mmatv":
		service = Service.MMATV
	else:
		raise InvalidService

	username = app.config['USERNAME']
	password = app.config['PASSWORD']
	server = app.config['SERVER']
	quality = app.config['QUALITY']

	auth_sign = AuthSign(service=service, auth=(username, password))
	guide = Guide()

	app.run(host='0.0.0.0', port=5004)
