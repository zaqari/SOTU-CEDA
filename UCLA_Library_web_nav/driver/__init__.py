import json
from typing import Union
import warnings
from tqdm import tqdm

import pandas as pd

from .driver_initialization import Initializer
from os.path import dirname, abspath
import time
# from random import randint

from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import logging

logger = logging.getLogger(__name__)
format = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
ch = logging.StreamHandler()
ch.setFormatter(format)
logger.addHandler(ch)


###################################################################################################
#### get facebook config
###################################################################################################
config_path = str(dirname(abspath(__file__)))+'/config.json'

with open(config_path, 'r') as f:
    config = json.load(f)
    f.close()

###################################################################################################
#### init a session
###################################################################################################
class session():

    def __init__(self, config: dict = config, browser_name: str = 'firefox', proxy: Union[str, None] = None, newspaper: str='LA Times'):
        super(session, self).__init__()
        self.config = config
        self.home = ''
        self.token_id = ''
        self.browser = browser_name
        self.headless = False
        self.proxy = proxy
        self.max_scrolls_on_page = 5
        self.timeout = 10
        self.wait_attempts = 3
        self.newspapers = []
        self.sotu = []
        self.mode = newspaper

        self.driver = self.new_session(
            config=self.config,
            browser_name=self.browser,
            headless=self.headless,
            proxy=self.proxy
        )

        self.driver.execute_script("document.body.style.zoom='50%'")

    def new_session(self, config: dict, browser_name: str, headless: bool, proxy: Union[str, None]):
        """Creates new session and logs in to WL"""
        driver = Initializer(browser_name=browser_name, headless=headless, proxy=proxy).init()
        # login(driver, config['username'], config['password'])
        if self.mode == 'LA Times':
            driver.get('https://www.proquest.com/latimes/advanced?accountid=14512')
        elif self.mode == 'OC Register':
            driver.get("https://search.library.ucla.edu/discovery/fulldisplay?context=L&vid=01UCS_LAL:UCLA&search_scope=ArticlesBooksMore&tab=Articles_books_more_slot&docid=alma9914328183506531")
        elif self.mode == 'UCSB':
            driver.get("https://www.presidency.ucsb.edu/documents/app-categories/spoken-addresses-and-remarks/presidential/state-the-union-addresses?items_per_page=60")
        return driver

    def get(self, page_name: str):
        self.driver.get(page_name)
        self.state_complete()

    def page_content(self):
        return self.driver.find_element(By.TAG_NAME, 'body').get_attribute('innerHTML')

    def set(self):
        self.home = self.driver.current_url
        if self.mode == 'LA Times':
            self.token_id = self.home.split('/')[5]

    def close_session(self):
        """Quits session and closes driver"""
        self.driver.close()
        self.driver.quit()

    def state_complete(self):
        """checks whether page is finished loading"""
        # try:
        state, tries = "", 0
        while (state != "complete") and (tries < 100):
            time.sleep(.01)
            state = self.driver.execute_script("return document.readyState")
        # except Exception as ex:
        #     logger.exception('Error at wait_until_completion: {}'.format(ex))

    def __detected_as_bot(self):
        try:
            self.driver.find_element(By.CSS_SELECTOR, 'iframe[title="reCAPTCHA"]')
            return True
        except Exception:
            return False

    def load_more(self, count: int = 5):
        for _ in range(count):
            self.__scroll()
            self.state_complete()

    def get_SOTU_links(self):
        elements = self.driver.find_elements(By.CSS_SELECTOR, 'div[class="node node-documents node-teaser view-mode-teaser "]')
        for element in elements:
            self.sotu += [
                {
                    'link': element.find_element(By.CSS_SELECTOR, 'a').get_attribute('href'),
                    'date': element.find_element(By.CSS_SELECTOR, 'span[class="date-display-single"]').text,
                    'president': element.find_element(By.XPATH, '//*[contains(text(), "Related")]').find_element(By.XPATH, '..').text.split('\n')[-1]
                }
            ]

        self.sotu = pd.DataFrame(self.sotu)

    def get_SOTU_content(self):
        warnings.filterwarnings("ignore")
        if 'text' not in list(self.sotu):
            self.sotu['text'] = None

        for idx in tqdm(self.sotu.loc[self.sotu['text'].isna()].index):
            link = self.sotu['link'].loc[idx]
            self.driver.get(link)
            self.state_complete()

            if self.__detected_as_bot():
                break

            try:
                content = self.driver.find_element(By.CSS_SELECTOR, 'div[class="field-docs-content"]')
                self.sotu['text'].loc[idx] = content.text

            except Exception:
                self.newspapers['text'].loc[idx] = None

        warnings.filterwarnings("default")

    def __proquest_next(self):
        self.driver.find_element(By.CSS_SELECTOR, 'a[title="Next Page"]').click()
        self.state_complete()
        self.home = self.driver.current_url
        self.collect_links()

    def proquest_iter_collect(self):
        self.set()
        self.proquest_collect_links()
        for _ in range(100):
            self.__proquest_next()

    def newsbank_collect(self):
        """
        div[class="search-hits"] -> a
        within each link: div[class="document-view__body read document-view__body--ascii "]
        :return:
        """
        main_content = self.driver.find_element(By.CSS_SELECTOR, 'div[class="search-hits"]')
        elements = main_content.find_elements(By.CSS_SELECTOR, 'h3[class="search-hits__hit__title search-hits__title"]')

    def __newsbank_next(self):
        0

    def proquest_collect_links(self):
        """findall: a[class="previewTitle Topicsresult "]
        get each item href
        get each item text
        get -> collect html from each item (div[id="fullTextZone"])
        """
        elements = self.driver.find_elements(By.CSS_SELECTOR, 'a[class="previewTitle Topicsresult "]')

        if len(self.newspapers) == 0:
            self.newspapers += [{'title':el.text, 'link': el.get_attribute('href').replace(self.token_id, '{}'), 'newspaper': self.mode} for el in elements]
            self.newspapers = pd.DataFrame(self.newspapers)

        else:
            new_df         = [{'title': el.text, 'link': el.get_attribute('href').replace(self.token_id, '{}'), 'newspaper': self.mode} for el in elements]
            self.newspapers = pd.concat([self.newspapers, pd.DataFrame(new_df)], ignore_index=True)

    def proquest_get_content(self):
        warnings.filterwarnings("ignore")

        if 'text' not in list(self.newspapers):
            self.newspapers['text'] = None

        for idx in tqdm(self.newspapers.loc[self.newspapers['text'].isna()].index):
            if not self.newspapers['text'].loc[idx]:
                link = self.newspapers['link'].loc[idx].format(self.token_id)
                self.driver.get(link)
                self.state_complete()

                if self.__detected_as_bot():
                    break

                try:
                    self.driver.find_element(By.CSS_SELECTOR, 'a[id="addFlashPageParameterformat_fulltext"]').click()
                except Exception:
                    0

                try:
                    content = self.driver.find_element(By.CSS_SELECTOR, 'div[id="readableContent"]')
                    self.newspapers['text'].loc[idx] = content.text

                except Exception:
                    self.newspapers['text'].loc[idx] = None

        warnings.filterwarnings("default")

    def newspapers_checkpoint(self, json_file_path: str):
        self.newspapers.to_json(json_file_path, orient='records')

    def load_newspapers_checkpoint(self, json_file_path: str):
        self.newspapers = pd.read_json(json_file_path)

    def sotu_checkpoint(self, json_file_path: str):
        self.sotu.to_json(json_file_path, orient='records')

    def load_sotu_checkpoint(self, json_file_path: str):
        self.sotu = pd.read_json(json_file_path)






