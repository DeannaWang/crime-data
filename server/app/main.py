from functools import wraps
from flask import Flask
from flask_restful import reqparse
from itsdangerous import (TimedJSONWebSignatureSerializer as Serializer)
from mongoengine import connect
from mongoengine.queryset.visitor import Q
from app.Tools import *
import json, itsdangerous

# Global constants and variables
CONN = connect('comp9321_ass2', host='mongodb://deanna:deanna@ds249249.mlab.com:49249/comp9321_ass2', username='deanna', password='deanna')
SECRET_KEY = "Dean Winchester"
NEXT_ID = get_max_id() + 1
POSTCODE_DICT = get_postcode_info()
FILE_LIST = get_filelist()
USERS = initialize_users()
OPTIONS_HEADER = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Accept, Content-Type, AUTH_TOKEN'
}

app = Flask(__name__)

def authenticate_by_token(token):
    if not token:
        return ''
    s = Serializer(SECRET_KEY)
    try:
        username = s.loads(token.encode())
    except itsdangerous.SignatureExpired:
        return '__token_is_expired__'
    if username in USERS:
        return username
    return ''

# Login as guest or admin
def login_required(f, message="Not authorized"):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        accept = request.headers.get('Accept')
        token = request.headers.get("AUTH_TOKEN")
        if not token:
            return response_for([], message, accept), 401
        username = authenticate_by_token(token)
        if username == '__token_is_expired__':
            return response_for([], 'Token expired', accept), 401
        if username in USERS:
            return f(*args, **kwargs)
        return response_for([], message, accept), 401
    return decorated_function

# Login as admin
def admin_required(f, message="Not authorized"):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        accept = request.headers.get('Accept')
        token = request.headers.get("AUTH_TOKEN")
        if not token:
            return response_for([], message, accept), 401
        username = authenticate_by_token(token)
        if username == 'admin':
            return f(*args, **kwargs)
        return response_for([], message, accept), 401
    return decorated_function

@app.route("/auth", methods=['POST', 'OPTIONS'])
def generate_token():
    if request.method == 'OPTIONS':
        header = OPTIONS_HEADER.copy()
        header['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        return Response(headers=header)
    parser = reqparse.RequestParser()
    parser.add_argument('username', type=str)
    parser.add_argument('password', type=str)
    args = parser.parse_args()
    username = args.get("username")
    password = args.get("password")
    s = Serializer(SECRET_KEY, expires_in=600)
    token = s.dumps(username)
    if username == 'admin' and password == USERS['admin'] or username == 'guest' and password == USERS['guest']:
        response = jsonify(info='Successfully logined as {0}'.format(username), token=token.decode())
        response.headers._list.append(('Access-Control-Allow-Origin', '*'))
        return response, 200
    response = jsonify(info='Login failed', token='')
    response.headers._list.append(('Access-Control-Allow-Origin', '*'))
    return response, 400

@app.route("/nsw_recorded_crime_statistics", methods=['OPTIONS'])
def root_options():
    header = OPTIONS_HEADER.copy()
    header['Access-Control-Allow-Methods'] = 'POST, GET, OPTIONS'
    return Response(headers=header)

@app.route("/nsw_recorded_crime_statistics", methods=['POST'])
@admin_required
def create_entry ():
    global NEXT_ID
    parser = reqparse.RequestParser()
    parser.add_argument('lgaName', type=str)
    parser.add_argument('postcode', type=str)
    args = parser.parse_args()
    lga = args.get("lgaName")
    postcode = args.get("postcode")
    accept = request.headers.get('Accept')
    if lga and postcode or not lga and not postcode:
        return response_for([], 'Input should be either lgaName or postcode', accept), 400
    lgas = []
    if lga:
        lgas.append(lga)
    else:
        lgas.extend(POSTCODE_DICT[postcode])
    matched_list, exist_list, not_found_list = get_matched_filenames(lgas, FILE_LIST)
    if len(not_found_list) == len(lgas):
        return response_for([], 'No such LGA name or postcode', accept), 400
    entries = []
    try:
        for file in matched_list:
            updated_time = datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
            entries.append(CrimeStatisticsOfLGA(NEXT_ID, updated_time, file, 'Created'))
            create_lga(format_lga(file) + 'lga.xlsx', NEXT_ID, updated_time)
            # Download file and save data asynchronously
            #thread = CreateLGAThread(NEXT_ID, format_lga(file) + 'lga.xlsx', updated_time)
            #thread.start()
            NEXT_ID += 1
    except:
        return response_for([], 'Database exception', accept), 500
    for exist in exist_list:
        entries.append(CrimeStatisticsOfLGA(exist[0], exist[2], exist[1], 'Exists'))
    entries = [json.loads(e.to_json().replace("\"_id\":", "\"id\":")) for e in entries]
    if not matched_list:
        return response_for(entries, 'Entry already exists', accept), 200
    return response_for(entries, 'Entry created', accept), 201

@app.route("/nsw_recorded_crime_statistics", methods=['GET'])
@login_required
def get_all_entries ():
    accept = request.headers.get('Accept')
    entries = [json.loads(e.to_json().replace("\"_id\":", "\"id\":")) for e in CrimeStatisticsOfLGA.objects]
    return response_for(entries, 'Success', accept), 200

@app.route("/nsw_recorded_crime_statistics/<entry_id>", methods=['OPTIONS'])
def entry_options(entry_id):
    header = OPTIONS_HEADER.copy()
    header['Access-Control-Allow-Methods'] = 'GET, DELETE, OPTIONS'
    return Response(headers=header)

@app.route("/nsw_recorded_crime_statistics/<entry_id>", methods=['DELETE'])
@admin_required
def delete_one_entry(entry_id):
    accept = request.headers.get('Accept')
    if not check_entry_id(entry_id):
        return response_for([], 'Invalid id', accept), 404
    CrimeStatisticsOfLGA.objects(id=entry_id)[0].delete()
    return response_for([], 'Entry deleted', accept), 200

@app.route("/nsw_recorded_crime_statistics/<entry_id>", methods=['GET'])
@login_required
def get_one_entry(entry_id):
    accept = request.headers.get('Accept')
    if not check_entry_id(entry_id):
        return response_for([], 'Invalid id', accept), 404
    entry_id = int(entry_id)
    matched_entry = CrimeStatisticsOfLGA.objects(id=entry_id)
    entries = [json.loads(e.to_json().replace("\"_id\":", "\"id\":")) for e in matched_entry]
    return response_for(entries, 'Success', accept), 200

@app.route("/nsw_recorded_crime_statistics/filter", methods=['OPTIONS'])
def filter_options():
    header = OPTIONS_HEADER.copy()
    header['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    return Response(headers=header)

@app.route("/nsw_recorded_crime_statistics/filter", methods=['GET'])
@login_required
def get_entries_with_filter():
    args = list(request.args.keys())
    accept = request.headers.get('Accept')
    if not args:
        return response_for([], 'Filter is empty', accept), 400
    and_list = re.findall(r'^lgaName[\s]+eq[\s]+((?:(?!(?:\band\b|\bor\b))[\s\S])+)[\s]+and[\s]+year[\s]+eq[\s]+([\d]{4})$', args[0])
    or_list = re.findall(r'lgaName[\s]+eq[\s]+((?:(?!\bor\b)[\s\S])+)', args[0])
    # Is query-type-two
    if and_list:
        lga = and_list[0][0].strip()
        year = and_list[0][1].strip()
        entries = list(CrimeStatisticsOfLGA.objects(Q(title__iexact=lga) &
                                                    Q(content__crime_statistics__data_of_year__year__=year)))
        if not entries:
            return response_for([], 'No such data', accept), 404
        entries[0].content.crime_statistics = [{
            'offence_group': cs.offence_group,
            'offence_type': cs.offence_type,
            'data_of_year': [[{
                'year': e['year'],
                'number_of_incidents': e['number_of_incidents'],
                'rate_per_100_000_population': e['rate_per_100_000_population']
            }] for e in cs.data_of_year if e.year == year][0]
        } for cs in entries[0].content.crime_statistics]
        entries = [json.loads(e.to_json().replace("\"_id\":", "\"id\":")) for e in entries]
        return response_for(entries, 'Success', accept), 200
    # Is query-type one
    if or_list:
        if any([s.strip() for s in re.findall(r'((?:(?!\bor\b|r\b)[\s\S])+)lgaName', args[0])]):
            return response_for([], 'Invalid filter format', accept), 400
        names = [e.strip() for e in or_list]
        if any([re.findall(r'(\band\b)', e) for e in names]) or len(re.findall(r'(\bor\b)', args[0])) != len(names) - 1:
            return response_for([], 'Invalid filter format', accept), 400
        entries = [json.loads(d.to_json().replace("\"_id\":", "\"id\":"))
                   for d in CrimeStatisticsOfLGA.objects(title__in=names)]
        if not entries:
            return response_for([], 'No such data', accept), 404
        return response_for(entries, 'Success', accept), 200
    return response_for([], 'Invalid filter format', accept), 400

if __name__ == "__main__":
    app.run()