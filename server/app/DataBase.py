from mongoengine import connect, MapField, IntField, StringField, \
    Document, EmbeddedDocument, ListField, EmbeddedDocumentField
from openpyxl import load_workbook
import re, os, requests

class StatisticsOfYear(EmbeddedDocument):
    year = StringField(regex='^[\d]{4}$')
    number_of_incidents = StringField(required=True, max_length=10)
    rate_per_100_000_population = StringField(required=True, max_length=10)

    def __init__(self, year, number_of_incidents, rate_per_100_000_population, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.year = year
        self.number_of_incidents = number_of_incidents
        self.rate_per_100_000_population = rate_per_100_000_population

class CrimeStatistics(EmbeddedDocument):
    offence_group = StringField(required=True, max_length=100)
    offence_type = StringField(max_length=100)
    data_of_year = ListField(EmbeddedDocumentField(StatisticsOfYear), required=True)
    other_info = MapField(StringField(max_length=20))

    def __init__(self, offence_group, data_of_year, offence_type = '', other_info = {}, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.offence_group = offence_group
        self.offence_type = offence_type
        self.data_of_year = data_of_year
        self.other_info = other_info

class CrimeStatisticsContent(EmbeddedDocument):
    headers = ListField(StringField(max_length=200))
    crime_statistics = ListField(EmbeddedDocumentField(CrimeStatistics), required=True)

    def __init__(self, headers, crime_statistics, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.headers = headers
        self.crime_statistics = crime_statistics

class CrimeStatisticsOfLGA(Document):
    id = IntField(primary_key=True)
    updated = StringField(required=True, max_length=50)
    title = StringField(required=True, max_length=100, default='', unique=True)
    content = EmbeddedDocumentField(CrimeStatisticsContent)
    #headers = ListField(StringField(max_length=200))
    #crime_statistics = ListField(EmbeddedDocumentField(CrimeStatistics), required=True)

    def __init__(self, id, updated, title, content = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.id = id
        self.updated = updated
        self.title = title
        if content:
            self.content = content

# Download the file and save data to mongodb
def create_lga(filename, id, updated):
    tmp = os.path.abspath(os.path.join(os.pardir, 'tmp'))
    if not os.path.exists(tmp):
        os.mkdir(tmp)
    base_url = 'http://www.bocsar.nsw.gov.au/Documents/RCS-Annual/'
    content=requests.get(base_url + filename).content
    with open(os.path.abspath(os.path.join(tmp, filename)), 'wb') as f:
       f.write(content)
    workbook = load_workbook(os.path.abspath(os.path.join(tmp, filename)), data_only=True)
    worksheet = workbook.active
    flag = False
    offence_group = None
    year_row = None
    lga = None
    headers = []
    crime_statistics = []
    for row in worksheet:
        if row[0].value is None and not flag:
            continue
        if not flag and row[0].value.find('Offence group') != -1:
            flag = True
            year_row = row[0].row - 1
            continue
        if not flag:
            headers.append(row[0].value)
            if row[0].value.endswith('Local Government Area'):
                lga = row[0].value[:-1 * len(' Local Government Area')]
            continue
        if flag and row[0].value is None and row[1].value is None:
            break
        data_of_year = []
        other_info = {}
        if row[0].value != None:
            offence_group = row[0].value
        offence_type = row[1].value.strip('^') if row[1].value is not None else ''
        for col in range(2, len(row), 2):
            if worksheet[year_row][col].value is not None:
                data_of_year.append(StatisticsOfYear(re.match('.*([\d]{4}).*', worksheet[year_row][col].value).group(1),
                                                     str(row[col].value), str(row[col + 1].value)))
            else:
                for rest_col in range(col, len(row)):
                    cell_data = row[rest_col].value
                    if isinstance(cell_data, float):
                        cell_data = '{0}%'.format(cell_data * 100)
                    else:
                        cell_data = cell_data.strip('^*')
                    other_info[worksheet[year_row + 1][rest_col].value.strip('^*')] = cell_data
                break
        crime_statistics.append(CrimeStatistics(offence_group, data_of_year, offence_type, other_info))
    content = CrimeStatisticsContent(headers, crime_statistics)
    connect('comp9321_ass2')
    CrimeStatisticsOfLGA(id, updated, lga, content).save()
    os.remove(os.path.abspath(os.path.join(tmp, filename)))