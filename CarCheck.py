#general
import sys
import time
import os
import re
from datetime import datetime

#email
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

#webcrawl
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

#data frame
import pandas as pd
import json


# Compare the old and new JSON data
def compare(oldJSON, newJSON):
    # Load JSON data into Python dictionaries (list of dicts)
    try:
        old_data = json.loads(oldJSON)
    except json.JSONDecodeError:
        old_data = []
    
    try:
        new_data = json.loads(newJSON)
    except json.JSONDecodeError:
        new_data = []

    # Convert lists of dictionaries into sets of frozensets (to allow set operations on dicts)
    old_set = {frozenset(item.items()) for item in old_data} if isinstance(old_data, list) else set()
    new_set = {frozenset(item.items()) for item in new_data} if isinstance(new_data, list) else set()

    # Compute additions and removals using set difference
    additions = new_set - old_set  # Items in new_data but not in old_data
    removals = old_set - new_set   # Items in old_data but not in new_data

    # Convert frozensets back into dictionaries for output
    arrivals = [dict(item) for item in additions]
    departures = [dict(item) for item in removals]

    return arrivals, departures


# Function to send an email notification
def send_email_notification(location_name, car):
    sender_email = "electricshingle@gmail.com"
    receiver_email = "edwardshingler@gmail.com"
    subject = f"New {car['Year']} {car['Make']} {car['Model']} at {location_name}"

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject

    body = f"Here is the car's info:\n\n\
    Location: {location_name}\n\
    Image: {car['Image']}\n\
    Year: {car['Year']}\n\
    Make: {car['Make']}\n\
    Model: {car['Model']}\n\
    Row: {car['Row']}\n\
    Set Date: {car['Set Date']}"

    msg.attach(MIMEText(body, 'plain'))

    # Setup the server (assuming Gmail, change if necessary)
    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    password = "iwdr apwq cthj fwom"

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, msg.as_string())
        server.quit()
        print("Email sent successfully.")
    except Exception as e:
        print(f"Failed to send email: {e}")

# Start the process
def checkPicknPull(checkList):
    options = webdriver.ChromeOptions()
    #options.headless = True  # Runs Chrome in headless mode (no GUI)
    driver = webdriver.Chrome(options=options)

    for member in checkList:
        member_location = member["Location"]
        print(member_location)
        driver.get(f'https://www.picknpull.com/check-inventory/vehicle-search?make=0&model=0&distance=25&zip={member_location}&year=')

        itx = 0
        while True:
            try:
                WebDriverWait(driver, 5).until(
                    EC.text_to_be_present_in_element((By.XPATH, "//*[@id='resultsList']"), "Pick-n-Pull - ")
                )
                print("Page Loaded")
                break
            except:
                if itx > 4:
                    print('There was an issue connecting with the website.')
                    break
                itx += 1
                print("Could not connect, trying again:", str(itx) + "/5")

        # Use BeautifulSoup for faster parsing
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        # Close the Selenium WebDriver
        driver.quit()

        # Locate the results list
        locations = soup.find_all('span', id='resultsList')

        for location in locations:
            # Extract the location
            location_name = location.find('a').get_text().strip()[14:]
            print(location_name)

            # Initialize the DataFrame
            df = pd.DataFrame(columns=["Image", "Year", "Make", "Model", "Row", "Set Date"])

            # Iterate through each row in the results list table
            for car in location.find_all('tr'):
                value_list = [td.get_text() for td in car.find_all('td')]
                # Only add the row if it has exactly 7 columns to match your DataFrame
                if len(value_list) == 7:
                    image_src = car.find('img')['src'] if car.find('img') else None
                    new_row = pd.DataFrame({
                        'Image': [image_src],
                        'Year': [value_list[1]], 
                        'Make': [value_list[2]], 
                        'Model': [value_list[3]], 
                        'Row': [value_list[4]], 
                        'Set Date': [value_list[5]]
                    })
                    df = pd.concat([df, new_row], ignore_index=True)

            print(df.info())

            # Load old JSON if it exists, or create an empty one
            try:
                with open(f"./{location_name}.json", "r") as file:
                    oldJSON = file.read()
            except FileNotFoundError:
                oldJSON = "{}"

            # Save the new data to JSON
            newJSON = df.to_json(orient='records')

            with open(f"./{location_name}.json", "w") as file:
                file.write(newJSON)

            # Compare old and new JSON and send an email if there's a change
            arrivals, departures = compare(oldJSON, newJSON)

            arrivals = [{**arrival,"Check Time":datetime.now().strftime("%H:%M %m/%d/%Y")} for arrival in arrivals]
            departures = [{**departure,"Check Time":datetime.now().strftime("%H:%M %m/%d/%Y")} for departure in departures]

            # Load old JSON if it exists, or create an empty one
            try:
                with open(f"./{location_name}_arrivals.json", "r") as file:
                    oldJSON = file.read()
            except FileNotFoundError:
                oldJSON = "[]"

            # Save the new data to JSON
            oldList = json.loads(oldJSON)
            newList = oldList + arrivals

            with open(f"./{location_name}_arrivals.json", "w") as file:
                file.write(json.dumps(newList))

            # Load old JSON if it exists, or create an empty one
            try:
                with open(f"./{location_name}_departures.json", "r") as file:
                    oldJSON = file.read()
            except FileNotFoundError:
                oldJSON = "[]"

            # Save the new data to JSON
            oldList = json.loads(oldJSON)
            newList = oldList + departures

            with open(f"./{location_name}_departures.json", "w") as file:
                file.write(json.dumps(newList))

            for item in member["Cars"]:
                print("CHECKING",item)
                years = []
                if item["yearSpan"] != "":
                    sub_spans = item["yearSpan"].split(',')
                    print(sub_spans)
                    for span in sub_spans:
                        if '-' in span:
                            start_end_year = span.split('-')
                            year_span = range(int(start_end_year[0]),int(start_end_year[1])+1)
                            years += year_span
                        else:
                            years += [int(span)]

                for arrival in arrivals:
                    if (
                        (arrival["Make"] == item["Make"]) &\
                        (arrival["Model"] == item["Model"]) &\
                        ((int(arrival["Year"]) in years) | (len(years)==0))\
                        ):
                        print("FOUND",arrival)
                        send_email_notification(location_name, arrival)
    

if __name__ == '__main__':
    checkList = [{
    "Member":"Eddie",
    "Location":"97266",
    "Cars":[{
        "Make":"Subaru",
        "Model":"Impreza",
        "yearSpan":"1998-2001"
        },
        {
        "Make":"Subaru",
        "Model":"Impreza Wagon",
        "yearSpan":"1998-2001"
        },
        {
        "Make":"Subaru",
        "Model":"Crosstrek",
        "yearSpan":"1998-2001"
        }]
    },
    {
    "Member":"David",
    "Location":"94305",
    "Cars":[{
        "Make":"Mazda",
        "Model":"MX-5 Miata",
        "yearSpan":"1996-1997"
        }]
    }]
    checkPicknPull(checkList)
