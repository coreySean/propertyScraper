from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
import time
import csv

lookForRentals = True
lookForSales = False

driver = webdriver.Firefox()

#filters out characters and converts to euro from RON where required
def FilterToCurrency(txt):
    txt = str(txt).lower()
    convertToEuro = 'ron' in txt or 'lei' in txt or 'leu' in txt
    txt = txt.split(',', 1)[0] #comma as decimal in europe
    txt = txt.replace('r','')
    txt = txt.replace('o','')
    txt = txt.replace('n','')
    txt = txt.replace('€','')
    txt = txt.replace(' ','')
    txt = txt.replace('.','')
    txt = txt.replace(',','')
    txt = txt.replace('e','')
    txt = txt.replace('u','')
    txt = txt.replace('/','')
    txt = txt.replace('l','')
    txt = txt.replace('u','')
    txt = txt.replace('n','')
    txt = txt.replace('ă','')
    if convertToEuro:
        txt = str(int(float(txt)*float(0.2)))
    return txt

#filters out junk from most common level descriptions
def FilterToLevel(txt):
    txt = str(txt).lower()
    if 'parter' in txt: #ground floor
        return '0'
    if 'demisol' in txt: #basement
        return '-1'
    txt = txt.split("/", 1)[0]
    txt = txt.replace(' ', '')
    txt = txt.replace('e','')
    txt = txt.replace('t','')
    txt = txt.replace('a','')
    txt = txt.replace('j','')
    return txt

#filters out junk from common area descriptions
def FilterToArea(area):
    area = area.split(".", 1)[0] #removes decimal part
    area = area.split(",", 1)[0] #remove decimal if decimal
    area = area.replace("'","")
    area = area.replace("\"","")
    area = area.replace('m','')
    area = area.replace('p','')
    area = area.replace(' ','')
    area = area.replace('²','')
    return area

#get all property links on page of each website
def GetLinksStoria(isRental):
    links = []

    #first website: storia.ro - rentals
    #storia is safe to use pages past limit
    #https://www.storia.ro/inchiriere/apartament/sibiu/?page=2
    for pageIndex in range(1,999):
        if isRental:
            driver.get('https://www.storia.ro/inchiriere/apartament/sibiu/?page='+str(pageIndex))
        else:
            driver.get('https://www.storia.ro/vanzare/apartament/sibiu/?page='+str(pageIndex))
        time.sleep(2)#sleep here as some of the fields get updated a second late
            
        if not 'page='+str(pageIndex) in driver.current_url and pageIndex > 1:
            #reached last page (redirects to first page)
            return links

        elements = driver.find_elements(By.CLASS_NAME, 'offer-item-title')
        for elems in elements:
            try:
                elem = elems.find_element(By.XPATH, '../..')#get second parent
                #make sure is not an advertised property
                if elem.get_attribute('data-featured-name') == 'listing_no_promo':
                    link = str(elem.get_attribute('href'))
                    #https://www.storia.ro/ro/oferta/apartament-2-camere-decomandat-construcie-nou-m-viteazul-lidl-IDpu4g.html#1e7a10e025
                    #storia puts some hashtag stuff after which is not important, need to filter it!
                    link = link.rsplit('#', 1)[0]
                    if not link in links:
                        links.append(link)
            except:
                pass

    return links

#returns an array with len > 1 on success, returns only link in array on fail
def ScrapeLinkStoriaRo(link):
    driver.get(link)
    time.sleep(3) #put this sleep here as it seems to not wait for the driver.get(link)
    scrapedDataRow = [] #this is the scraped data per link
    #price
    try:
        price = FilterToCurrency(WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '.css-unc98a.e176pl9r7'))
            ).get_attribute('innerHTML'))
        #check if is numeric
        if (price.isnumeric()):
            scrapedDataRow.append(price)
        else:
            #no price, don't proceed
            log(f'Scrape failed for link: {link} --> price not numeric: {price}')
            return [link]
    except:
        #no price, don't proceed
        log(f'Scrape failed for link: {link} --> price not found')
        return [link]

    #area
    try:
        area = driver.find_element(By.XPATH, "//div[@aria-label='Suprafata utila (m²)']")
        area = area.find_element(By.XPATH, "./div[contains(@class,'ev4i3ak0')]")
        area = str(area.get_attribute('innerHTML'))
        area = FilterToArea(area)
        #check if is numeric
        if (area.isnumeric()):
            scrapedDataRow.append(area)
        else:
            #no area, don't proceed
            log(f'Scrape failed for link: {link} --> area not numeric: {area}')
            return [link]

    except:
        #no area, don't proceed
        log(f'Scrape failed for link: {link} --> area not found')
        return [link]

    #number of rooms
    try:
        rooms = driver.find_element(By.XPATH, "//div[@aria-label='Numarul de camere']")
        rooms = rooms.find_element(By.XPATH, "./div[contains(@class,'ev4i3ak0')]")
        rooms = str(rooms.get_attribute('innerHTML'))
        rooms = rooms.replace(' ','')
        #check if is numeric
        if not (rooms.isnumeric()):
            #default to '1'
            rooms = '1'
        scrapedDataRow.append(rooms)
    except:
        log(f'Handled error for link: {link} --> bedrooms not found')
        rooms = '1'
        scrapedDataRow.append(rooms)

    #number of bathrooms
    try:
        bathrooms = driver.find_element(By.XPATH, "//div[@aria-label='Numarul de bai']")
        bathrooms = bathrooms.find_element(By.XPATH, "./div[contains(@class,'ev4i3ak0')]")
        bathrooms = str(bathrooms.get_attribute('innerHTML'))
        bathrooms = bathrooms.replace(' ','')
        #check if is numeric
        if not (bathrooms.isnumeric()):
            #default to '1'
            bathrooms = 1
        scrapedDataRow.append(bathrooms)
    except:
        #default to '1'
        log(f'Handled error for link: {link} --> bathrooms not found')
        bathrooms = 1
        scrapedDataRow.append(bathrooms)

    #level (floor)
    try:
        level = driver.find_element(By.XPATH, "//div[@aria-label='Etaj']")
        level = level.find_element(By.XPATH, "./div[contains(@class,'ev4i3ak0')]")
        level = str(level.get_attribute('innerHTML'))
        level = FilterToLevel(level)
        #check if is numeric
        if not (level.isnumeric()):
            #default to 0
            level = 0
        scrapedDataRow.append(level)
    except:
        #default to 0
        log(f'Handled error for link: {link} --> Level not found')
        level = 0
        scrapedDataRow.append(level)
    
    #add link for reference
    scrapedDataRow.append(link)
    return scrapedDataRow

#appends some log text to the log file
#this script runs for some time.
#need to be able to safely copy file during runtime for analysis
def log(text):
    with open("./data/log.csv", "a") as file:
        file.write(datetime.now().strftime("%m/%d/%Y") + ', '+text+'\n')
        file.close()

#appends scraped data to csv
def AppendCSV(dataToAppend, isRental):
    if isRental:
        dataToAppend.insert(0, datetime.now().strftime("%m/%d/%Y"))
        with open("./data/rental.csv", "a") as file:
            writer = csv.writer(file, delimiter = ',')

            #write data
            writer.writerow(dataToAppend)
            file.close()
    else:
        dataToAppend.insert(0, datetime.now().strftime("%m/%d/%Y"))
        with open("./data/purchase.csv", "a") as file:
            writer = csv.writer(file, delimiter = ',')

            #write data
            writer.writerow(dataToAppend)
            file.close()
        

#attempts to return links to scrape from imobiliar
def GetLinksImobiliarRo(isRental):
    links = []
    try:
        for pageIndex in range(1,999):
            if isRental:
                driver.get('https://www.imobiliare.ro/inchirieri-apartamente/sibiu?pagina=' + str(pageIndex))
            else:
                driver.get('https://www.imobiliare.ro/vanzare-apartamente/sibiu?pagina=' + str(pageIndex))
            time.sleep(2)
            
            if not 'pagina='+str(pageIndex) in driver.current_url:
                return links

            elements = driver.find_elements(By.XPATH, "//h2[contains(@class, 'titlu-anunt') and contains(@class, 'hidden-xs')]/a")
            for element in elements:
                try:
                    link = str(element.get_attribute('href'))
                    if isRental and not 'vanzare' in link and not link in links: #sometimes they advertise units for sale on rental page
                        links.append(link)
                    if not isRental and 'vanzare' in link and not link in links:
                        links.append(link)
                except:
                    #do nothing
                    pass
        return links #we got here without doubling up
    except:
        return links #return whatever links we have

#returns array with only [link] on fail
def ScrapeImobiliarRo(link):
    try:
        driver.get(link)
        time.sleep(5)
        #price
        data = [0,0,0,0,0,link] #need to initialize due to unknown order of data
        price = None
        #wrapper_pret_rate
        print('searching for element')
        price = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '.pret.first.blue'))
            )
        price = price.get_attribute('textContent')
        #now we have price in 3 currencies:
        #2.226 RON515 USD450 EUR / lună
        #filter out everything after RON
        price = price.lower()
        head, sep, tail = price.partition('ron')
        price = head + sep
        price = FilterToCurrency(price)
        data[0] = price
        if not price.isnumeric:
            log(f'Scrape failed for link: {link} --> price not numeric: {price}')
            return [link]

        tables = driver.find_elements(By.CLASS_NAME, 'lista-tabelara')
        #may be more than one table, no guarantee important info is on table 1.
        #want to iterate each li in table to find text
        lists = [] #list of elements for list items <li>
        for table in tables:
            temp = table.find_elements(By.TAG_NAME, 'li')
            for tmp in temp:
                lists.append(tmp)
        for list in lists:
            text = str(list.get_attribute('innerHTML'))
            text = text.lower() #make lowercase
            #area,rooms,bathrooms,level,link
            if 'utilă' in text:
                value = list.find_element(By.XPATH, './span').get_attribute('innerHTML')
                data[1] = FilterToArea(value)
            elif 'camer' in text:
                value = str(list.find_element(By.XPATH, './span').get_attribute('innerHTML'))
                value = FilterToArea(value) #simplest filter for unwanted characters
                data[2] = value
            elif 'băi' in text:
                try:
                    value = str(list.find_element(By.XPATH, './span').get_attribute('innerHTML'))
                    value = FilterToArea(value) #simplest filter for unwanted characters
                    data[3] = value
                except:
                    data[3]=1
            elif 'etaj' in text:
                try:
                    value = str(list.find_element(By.XPATH, './span').get_attribute('innerHTML')).lower()
                    value = FilterToLevel(value)
                    if not (value.isnumeric()):
                        #default to 0
                        level = 0
                    data[4] = value
                except:
                    data[4] = 0
        return data
    except:
        log(f'Scrape failed for link: {link}')
        return [link]

def start():
    ignoredLinks = 0
    if lookForRentals:
        links = []
        #1) check for links in rental.csv
        with open('./data/rental.csv', 'r') as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            for row in csv_reader:
                links.append(row[6])
        csv_file.close()

        #2) look for new links
        newlinks = []
        for tmp in GetLinksStoria(True):
            if not tmp in links:
                newlinks.append(tmp)
            else:
                #log(f'link ignored (duplicate): {link}' ) #all working, not logging anymore
                ignoredLinks = ignoredLinks+1

        for tmp in GetLinksImobiliarRo(True):
            if not tmp in links:
                newlinks.append(tmp)
            else:
                #log(f'link ignored (duplicate): ' + tmp ) #all working, not logging anymore
                pass
        
        for link in newlinks:
            links.append(link)
        
        #3) scrape new links
        for link in newlinks:
            data = []
            if 'storia' in link:
                data = ScrapeLinkStoriaRo(link)
            elif 'imobiliare' in link:
                data = ScrapeImobiliarRo(link)
            if len(data) > 1:
                #valid data
                AppendCSV(data, True)
            else:
                pass
                log(f'Scrape failed for link: {link}')
        log(f'total links ignored (rental): {ignoredLinks}')
    ignoredLinks = 0
    if lookForSales:
        links = []
        #1) check for links in purchase.csv
        with open('./data/purchase.csv', 'r') as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=',')
            for row in csv_reader:
                links.append(row[6])
        csv_file.close()

        #2) look for new links
        newlinks = []
        for tmp in GetLinksStoria(False):
            if not tmp in links:
                newlinks.append(tmp)
            else:
                ignoredLinks = ignoredLinks+1
        for tmp in GetLinksImobiliarRo(False):
            if not tmp in links:
                newlinks.append(tmp)
            else:
                ignoredLinks = ignoredLinks+1
        
        for link in newlinks:
            links.append(link)
        
        #3) scrape new links
        for link in newlinks:
            data = []
            if 'storia' in link:
                data = ScrapeLinkStoriaRo(link)
            elif 'imobiliare' in link:
                data = ScrapeImobiliarRo(link)
            if len(data) > 1:
                #valid data
                AppendCSV(data, False)
        log(f'total links ignored (purchase): {ignoredLinks}')


start()
driver.close()
exit()

                


