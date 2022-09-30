import os
import csv
import string
import tempfile
import getpass
import subprocess
import re

import requests
import bs4
from bw2io import SingleOutputEcospold2Importer, bw2setup
from bw2data import projects, databases

from eidl.storage import eidlstorage
from eidl.settings import Settings


class EcoinventDownloader:
    def __init__(self, username=None, password=None, version=None,
                 system_model=None, outdir=None, store_download=True, **kwargs):
        settings = Settings()
        self.username = username or settings.username
        self.password = password or settings.password.get_secret_value() if settings.password else None
        self.version = version or settings.version
        self.system_model = system_model or settings.system_model
        self.outdir = outdir or settings.output_path
        self.store_download = store_download
        if self.username is None or self.password is None:
            self.username, self.password = self.get_credentials()
        self.post_download_hook = lambda path, filename: (path, filename)

    def run(self):
        if self.check_stored():
            return

        self.login()
        print('login successful!')

        if (self.version, self.system_model) not in self.db_dict.keys():
            self.version, self.system_model = self.choose_db()
        if self.check_stored():
            return

        print('downloading ei-{}-{} ...'.format(self.version, self.system_model))
        self.download()
        print('download finished!: {}\n'.format(self.out_path))

    def get_db_sui(self, spdx: str):
        """
        From the given spdx string, get the version and system model
        :param spdx:
        :return:
        """
        system_models = set([vsm[1] for vsm in self.db_dict])
        if re.match(rf'ei-\d.\d-[{("|".join(system_models))}]', spdx) is None:
            raise KeyError('The provided database name does not have the correct format.'
                           'Use ei-<version>-<system model>. '
                           'System models are ["cutoff", "apos", "consequential", "EN15804"]')

        db_sui_db, db_sui_version, db_sui_sm = spdx.split('-')
        available_spdx = [f'ei-{tup[0]}-{tup[1]}' for tup in self.db_dict.keys()]
        if not (db_sui_version, db_sui_sm) in self.db_dict.keys():
            raise KeyError(f'The provided database does not exist online.'
                           f'Choose one of the following: {available_spdx}')
        return db_sui_version, db_sui_sm

    def _download_mapping(self, spdx, saveto):
        self._download_one(f'https://ecoinvent.org/public/{spdx}_url_ids.csv', saveto)
        #!FIXME: what if 404 because not 3.8

    def get_pdf(self, activity_name, geography, reference_product):
        """
        Given the input parameters, download a PDF from ecoinvent's website.
        :param activity_name
        :param geography
        :param reference_product
        """
        spdx = f'ei-{self.version}-{self.system_model}'
        file_path = os.path.join(eidlstorage.eidl_dir, f'{spdx}_url_ids.csv')
        if not os.path.exists(file_path):
            self._download_mapping(spdx=spdx, saveto=file_path)
        with open(file_path, mode='r') as f:
            csvfile = csv.reader(f)
            for line in csvfile:
                if line[0:3] == [activity_name, geography, reference_product]:
                    pdf_id = line[-1]
                    break
        pdf_url = self._get_pdf_url(self.version, pdf_id)
        pdf_filename = f'ei-{self.version}-{self.system_model} {activity_name}-{geography}-{reference_product}.pdf'
        self._download_one(pdf_url, pdf_filename)

    @property
    def file_name(self):
        fn = 'ei-{}-{}.7z'.format(self.version, self.system_model)
        return fn

    def check_stored(self):
        if self.file_name in eidlstorage.stored_dbs:
            self.out_path = eidlstorage.stored_dbs[self.file_name]
            print('database already downloaded')
            return True
        else:
            return False

    def get_credentials(self):
        if not self.username:
            un = input('ecoinvent username: ')
        else:
            un = self.username
        pw = getpass.getpass('ecoinvent password: ')
        return un, pw

    def login(self):
        print('logging in to ecoinvent homepage...')
        if self.username is None or self.password is None:
            self.username, self.password = self.get_credentials()
        self.session = requests.Session()
        logon_url = 'https://v38.ecoquery.ecoinvent.org/Account/LogOn'
        post_data = {'UserName': self.username,
                     'Password': self.password,
                     'IsEncrypted': 'false',
                     'ReturnUrl': '/'}
        try:
            self.session.post(logon_url, post_data, timeout=20)
        except (requests.ConnectTimeout, requests.ReadTimeout, requests.ConnectionError) as e:
            self.handle_connection_timeout()
            raise e

        success = bool(self.session.cookies)
        self.login_success(success)

    def login_success(self, success):
        if not success:
            print('Login failed')
            self.username, self.password = self.get_credentials()
            self.login()

    def handle_connection_timeout(self):
        print('The request timed out, please check your internet connection!')
        if eidlstorage.stored_dbs:
            print(
                'You have the following databases stored:\n\t{}\n'.format(
                    '\n\t'.join(eidlstorage.stored_dbs.keys())) +
                'You can use these offline by adding the corresponding `version` and `system_model` keywords\n' +
                "Example: eidl.get_ecoinvent(version='3.5', system_model='cutoff')"
            )

    def get_available_files(self):
        files_url = 'https://v38.ecoquery.ecoinvent.org/File/Files'
        try:
            files_res = self.session.get(files_url, timeout=20)
        except (requests.ConnectTimeout, requests.ReadTimeout, requests.ConnectionError) as e:
            self.handle_connection_timeout()
            raise e
        soup = bs4.BeautifulSoup(files_res.text, 'html.parser')
        all_files = [l for l in soup.find_all('a', href=True) if
                     l['href'].startswith('/File/File?')]
        not_allowed = soup.find_all('a',  class_='fileDownloadNotAllowed')
        available_files = set(all_files).difference(set(not_allowed))
        link_dict = {f.contents[0]: f['href'] for f in available_files}
        link_dict = {
            k.replace('-', ''):v for k, v in link_dict.items() if k.startswith('ecoinvent ') and
            k.endswith('ecoSpold02.7z') and not 'lc' in k.lower()
        }
        db_dict = {
            tuple(k.replace('ecoinvent ', '').split('_')[:2:]): v for k, v in link_dict.items()
        }
        return db_dict

    def choose_db(self):
        versions = {k[0] for k in self.db_dict.keys()}
        version_dict = dict(zip(string.ascii_lowercase,
                                sorted(versions, reverse=True)))
        print('\n', 'available versions:')
        for k, version in version_dict.items():
            print(k, version)
        while True:
            version = input('version: ')
            if version in versions or version in version_dict.keys():
                break
            else:
                print('Enter version number or letter')
        system_models = {k[1] for k in self.db_dict.keys() if k[0] == version_dict.get(version, version)}
        sm_dict = dict(zip(string.ascii_lowercase, sorted(system_models)))
        print('\n', 'system models:')
        for k, sm in sm_dict.items():
            print(k, sm)
        while True:
            sm = input('system model: ')
            if sm in system_models or sm in sm_dict.keys():
                break
            else:
                print('Enter system model or letter')
        dbkey = (version_dict.get(version, version),
                 sm_dict.get(sm, sm))
        return dbkey

    def _download_one(self, url: str, output_file_name: str):
        """
        Download a file given the full URL

        :param url: the full/absolute url
        :param output_file_name: the name of the output file
        :return:
        """
        print(f'Downloading {url}')
        try:
            file_content = self.session.get(url, timeout=60).content
        except (requests.ConnectTimeout, requests.ReadTimeout, requests.ConnectionError) as e:
            self.handle_connection_timeout()
            raise e

        if self.outdir:
            self.out_path = os.path.join(self.outdir, output_file_name)
        else:
            self.out_path = os.path.join(os.path.abspath('.'), output_file_name)

        with open(self.out_path, 'wb') as out_file:
            out_file.write(file_content)

    def _get_pdf_url(self, db_version, pdf_id):
        db_num = db_version.replace('.', '')
        return f'https://v{db_num}.ecoquery.ecoinvent.org/Details/PDF/{pdf_id}'

    def _get_pdf_url(self, db_version, pdf_id):
        db_num = db_version.replace('.', '')
        return f'https://v{db_num}.ecoquery.ecoinvent.org/Details/PDF/{pdf_id}'

    def download(self):
        with tempfile.TemporaryDirectory() as td:
            download_path = self.outdir
            if download_path is None:
                if self.store_download:
                    download_path = eidlstorage.eidl_dir
                else:
                    download_path = td


            url = 'https://v38.ecoquery.ecoinvent.org'
            db_key = (self.version, self.system_model)
            try:
                file_content = self.session.get(url + self.db_dict[db_key], timeout=60).content
            except (requests.ConnectTimeout, requests.ReadTimeout, requests.ConnectionError) as e:
                self.handle_connection_timeout()
                raise e

            self.out_path = os.path.join(download_path, self.file_name)

            with open(self.out_path, 'wb') as out_file:
                out_file.write(file_content)

            self.extract(target_dir=download_path)

            self.post_download_hook(download_path, self.file_name)

    def extract(self, target_dir, **kwargs):
        extract_cmd = ['py7zr', 'x', self.out_path, target_dir]
        try:
            self.extraction_process = subprocess.Popen(extract_cmd, **kwargs)
            return self.extraction_process.wait()
        except FileNotFoundError as e:
            if "PYCHARM_HOSTED" in os.environ:
                print('It appears the EcoInventDownLoader is run from PyCharm. ' +
                      'Please make sure you select the the correct conda environment ' +
                      'as your project interperter or run your script/command in a ' +
                      'Python console outside of PyCharm.')
            raise e

    def set_with_spdx(self, spdx: str):
        self.version, self.system_model = self.get_db_sui(spdx)


def get_ecoinvent(db_name=None, auto_write=False, outdir=None, download_path=None, store_download=True, **kwargs):
    """
    Download and import ecoinvent to current brightway2 project
    Args:
        db_name: name to give imported database (string), can only be of the pattern "ei-<version>-<system_model>". If no entry is given, the name is based on the chosen version and system model
        auto_write: automatically write database if no unlinked processes (boolean) default is False (i.e. prompt yes or no)
        outdir: path to download .7z file to (string) default is download to temporary directory
        store_download: store the .7z file for later reuse, default is True, only takes effect if no download_path is provided
        username: ecoinvent username (string)
        password: ecoivnent password (string)
        version: ecoinvent version (string), eg '3.5'
        system_model: ecoinvent system model (string), one of {'cutoff', 'apos', 'consequential'}
    Optional kwargs:
        username: ecoinvent username (string)
        password: ecoivnent password (string)
        version: ecoinvent version (string), eg '3.5'
        system_model: ecoinvent system model (string), one of {'cutoff', 'apos', 'consequential'}
    """
    downloader = EcoinventDownloader(outdir=download_path, store_download=store_download, **kwargs)
    importer = None
    downloader.login()
    downloader.db_dict = downloader.get_available_files()

    def process_file(path, file_name):
        nonlocal importer
        nonlocal db_name

        if db_name:
            downloader.set_with_spdx(db_name)
        if not db_name:
            db_name = f'ei-{downloader.version}-{downloader.system_model}'
        datasets_path = os.path.join(path, 'datasets')
        importer = SingleOutputEcospold2Importer(datasets_path, db_name)

    downloader.post_download_hook = process_file
    downloader.run()

    if 'biosphere3' not in databases:
        if auto_write:
            bw2setup()
        else:
            print('No biosphere database present in your current ' +
                  'project: {}'.format(projects.current))
            print('You can run "bw2setup()" if this is a new project. Run it now?')
            if input('[y]/n ') in {'y', ''}:
                bw2setup()
            else:
                return

    importer.apply_strategies()
    datasets, exchanges, unlinked = importer.statistics()

    if auto_write and not unlinked:
        print('\nWriting database {} in project {}'.format(
            db_name, projects.current))
        importer.write_database()
    else:
        print('\nWrite database {} in project {}?'.format(
            db_name, projects.current))
        if input('[y]/n ') in {'y', ''}:
            importer.write_database()


def get_ecoinvent_cli():
    downloader = EcoinventDownloader()
    downloader.run()


def get_pdf(spdx, activity_name, geography, reference_product, **kwargs):
    """
    Download a PDF file identified with the given params
    :param spdx: the spdx string to identify ecoinvent's version and system model
    :param activity_name: the activity name
    :param geography: the geography
    :param reference_product: the reference product
    """
    downloader = EcoinventDownloader(**kwargs)
    downloader.login()
    downloader.db_dict = downloader.get_available_files()
    downloader.set_with_spdx(spdx)
    downloader.get_pdf(activity_name, geography, reference_product)
