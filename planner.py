
import json, re, requests, re, time
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time as t
import sqlite3
import matplotlib.pyplot as plt

date_format = "%d-%m-%Y"
datetime_format = "%d-%m-%Y %H:%M:%S"
estonia_URL = "https://www.kava.ee/telekava/eesti/"
serials_URL = "https://www.kava.ee/telekava/sarjad/"
sports_URL = "https://www.kava.ee/telekava/Sport/"
sections = ['estonia', 'serials', 'sports']

def createDatabaseConnection():
    return sqlite3.connect("schedule.db")

def updateData(connection, dates, dates_sections):
    connection.execute('''CREATE TABLE IF NOT EXISTS SHOWS
                        (SECTION VARCHAR(10) NOT NULL,
                        CHANNEL VARCHAR(50) NOT NULL,
                        SHOW VARCHAR(100) NOT NULL,
                        DESCRIPTION VARCHAR(100),
                        SEASON INTEGER,
                        EPISODE INTEGER,
                        DATE VARCHAR(10) NOT NULL,
                        DURATION VARCHAR(10) NOT NULL);
                        ''')
    connection.commit()
    print('Table "SHOWS" in database.')

    dates_already_in_db = connection.execute("SELECT DISTINCT DATE FROM SHOWS").fetchall()
    dates_already_in_db = [r[0] for r in dates_already_in_db]
    dates_to_remove = tuple(list(set(dates_already_in_db) - set(dates)))
    if len(dates_to_remove) == 1:
        dates_to_remove = str(dates_to_remove).replace(",", "")
    connection.execute('DELETE FROM SHOWS WHERE DATE NOT IN {}'.format(dates_to_remove))
    connection.commit()
    print("Number of out-of-date lines removed during database update:", len(dates_to_remove))

    for date in dates:
        for i in range(3):
            section_data = dates_sections[date][i]
            for channel_name in section_data:
                data_parts = section_data[channel_name]
                for dp in data_parts:
                    check_sql = 'SELECT COUNT(*) FROM SHOWS WHERE (SECTION = ? AND CHANNEL = ? AND SHOW = ? AND DESCRIPTION = ? AND SEASON = ? AND EPISODE = ? AND DATE = ? AND DURATION = ?)'
                    check = connection.execute(check_sql, (sections[i], dp[0], dp[1], dp[2], dp[3], dp[4], date, dp[5])).fetchall()
                    if check[0][0] == 0:
                        insert_sql = 'INSERT INTO SHOWS (SECTION, CHANNEL, SHOW, DESCRIPTION, SEASON, EPISODE, DATE, DURATION) VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
                        connection.execute(insert_sql, (sections[i], dp[0], dp[1], dp[2], dp[3], dp[4], date, dp[5]))
    connection.commit()
    total_lines = connection.execute('SELECT COUNT(*) FROM SHOWS').fetchall()
    print("Total lines in database:", total_lines[0][0])

#TODO to consider also today's schedule
def getCurrentDateTime():
    return datetime.today().strftime(date_format)

def getPastTwoWeeksDates():
    return [(datetime.today() - timedelta(days = i)).strftime(date_format) for i in range(1, 15)]

def getJSONData(url):
    data = requests.get(url)
    data_text = data.text
    soup = BeautifulSoup(data_text, "html.parser")
    soup_string = str(soup)
    content_line = re.search("window.cacheSchedule.*", soup_string)
    if content_line:
        content_line_group = content_line.group()
        content_json_string = content_line_group.replace("window.cacheSchedule = ", "")[:-1]
        content_json = json.loads(content_json_string)
    return content_json["data"]

def processData(data):
    dictionary_of_data_lists = dict()
    list_for_data_list = []
    for d in data:
        schedule = d["schedule"]
        if len(schedule) > 0:
            channel = d["channel"]["name"]
            for s in schedule:
                start_time = time.strftime(datetime_format, time.localtime(int(s["start_unix"])))
                end_time = time.strftime(datetime_format, time.localtime(int(s["stop_unix"])))
                duration = datetime.strptime(end_time, datetime_format) - datetime.strptime(start_time, datetime_format)
                show = s["t"]
                description = "NULL"
                season = s["se"]
                episode = s["ep"]
                if "cs" in s:
                    description = s["cs"]
                list_for_data_list.append([channel, show, description, season, episode, str(duration)])
            dictionary_of_data_lists[channel] = list_for_data_list
            list_for_data_list = []
    return dictionary_of_data_lists

def getData(dates_of_past_two_weeks):
    dictionary_dates_sections = dict()
    for date in dates_of_past_two_weeks:
        data_estonia = getJSONData(estonia_URL + date)
        data_serials = getJSONData(serials_URL + date)
        data_sports = getJSONData(sports_URL + date)
        result_estonia = processData(data_estonia)
        result_serials = processData(data_serials)
        result_sports = processData(data_sports)
        dictionary_dates_sections[date] = [result_estonia, result_serials, result_sports]
    return dictionary_dates_sections

def getCertainChannelData(connection, section, channel):
    return connection.execute('SELECT * FROM SHOWS WHERE SECTION = \"{}\" AND CHANNEL = \"{}\"'.format(section, channel)).fetchall()

def getAllChannelVariants(connection, variant, section):
    return connection.execute('SELECT DISTINCT {} FROM SHOWS WHERE SECTION = \"{}\"'.format(variant, section)).fetchall()

def start():
    print("Starting TV schedule planner.")
    connection_with_db = createDatabaseConnection()
    past_two_week_dates = getPastTwoWeeksDates()
    print("Updating database...\n")
    data = getData(past_two_week_dates)
    updateData(connection_with_db, past_two_week_dates, data)
    connection_with_db.close()

def startOnlyRequests():
    print("Starting TV schedule planner.")
    past_two_week_dates = getPastTwoWeeksDates()
    print("Updating database...\n")
    getData(past_two_week_dates)

def communication(section_interested):
    new_connection_with_db = createDatabaseConnection()
    user_selection_section_e = input('Are you interested in "{}" section channels (Y/N)?'.format(section_interested))
    if user_selection_section_e == "Y":
        print("Select which channels are you interested in (enter the number(s), non-integer or out of range integer input finishes choosing). Possible variants:\n")
        variants = getAllChannelVariants(new_connection_with_db, "CHANNEL", section_interested)
        variant_integers = [v for v in range(len(variants))]
        for vi in variant_integers:
            print("Channel:", variants[vi][0], "[{}]".format(vi))
        channels_e_interested = []
        while True:
            ci = input()
            if re.match("\d+", ci):
                number = int(ci)
                if number in variant_integers:
                    channels_e_interested.append(variants[number][0])
            else:
                break
        interested_channels_statement = 'You are interested in the following channels of section "{}": '.format(section_interested)
        for c in channels_e_interested:
            interested_channels_statement += (c + ", ")
        interested_channels_statement = interested_channels_statement[:-2] + "."
        shows_serials_e_interested = dict()
        print(channels_e_interested)
        for ch in channels_e_interested:
            print("Choose shows/serials of channel {} you are interested in (enter the number(s), non-integer or out of range integer input finishes choosing). Possible variants:\n".format(ch))
            channel_data_selected = getCertainChannelData(new_connection_with_db, section_interested, ch)
            variants_shows_serials_integers = [cds for cds in range(len(channel_data_selected))]
            for vssi in variants_shows_serials_integers:
                print("Show/serial:", channel_data_selected[vssi], "[{}]".format(vssi))
            while True:
                si = input()
                if re.match("\d+", si):
                    number_si = int(si)
                    if number_si in variants_shows_serials_integers:
                        if ch not in shows_serials_e_interested:
                            shows_serials_e_interested[ch] = [channel_data_selected[number_si]]
                        else:
                            current = shows_serials_e_interested[ch]
                            current.append(channel_data_selected[number_si])
                            shows_serials_e_interested[ch] = current
                else:
                    break
        for chl in shows_serials_e_interested:
            print('You are interested in the following shows/serials of channel {}:\n'.format(chl))
            for c in shows_serials_e_interested[chl]:
                print((c[2] + " (season " + str(c[4]) + ", episode " + str(c[5]) + ", date: " + c[6] + ", duration: " + c[7] + ")"))
        return shows_serials_e_interested

def measureRequestsAndDatabase():
    times = []
    execution_tests = []
    for m in range(10):
        print(m)
        s = t.time()
        start()
        e = t.time()
        times.append(e - s)
        execution_tests.append("Execution test {}".format(m)) 
        #Wait 20 second not to send too many requests in a short time.
        t.sleep(20)
    plt.bar(execution_tests, times)
    plt.title("Time took vs program execution (test n)")
    plt.xlabel("test number")
    plt.ylabel("time")
    plt.show()

def measureRequests():
    times = []
    execution_tests = []
    for m in range(10):
        print(m)
        s = t.time()
        start()
        e = t.time()
        times.append(e - s)
        execution_tests.append("Execution test {}".format(m)) 
        #Wait 20 second not to send too many requests in a short time.
        t.sleep(20)
    plt.bar(execution_tests, times)
    plt.title("Time took vs program execution (test n)")
    plt.xlabel("test number")
    plt.ylabel("time")
    plt.show()

#measureRequestsAndDatabase()
#measureRequests()

#Reference: https://stackoverflow.com/questions/4632322/finding-all-possible-combinations-of-numbers-to-reach-a-given-sum

def main():
    def calculateSumVariants(durations, time, partial=[]):
        s = sum(partial)
        if s <= time: 
            if len(partial) > 0:
                all_possible_max_variants.append(partial)
        if s >= time:
            return
        for i in range(len(durations)):
            n = durations[i]
            remaining = durations[i + 1:]
            calculateSumVariants(remaining, time, partial + [n]) 
    start()
    all_interested = []
    for sec in sections:
        com = communication(sec)
        for com1 in com:
            for com2 in com[com1]:
                all_interested.append(((com2[2] + " (season " + str(com2[4]) + ", episode " + str(com2[5]) + ", date: " + com2[6] + ")"), com2[7]))
    print("The shows/serials you are interested in are the following:")
    for ai in range(len(all_interested)):
        print(all_interested[ai][0], "[{}]".format(ai))
    priority_integers = [pi for pi in range(len(all_interested))]
    user_priorities = []
    print("Enter the integers followed by each selected show/serial in order of your priority (the lowest the more important):")
    while len(user_priorities) < len(priority_integers):
        p = input()
        if re.match("\d+", p):
            numberp = int(p)
            if numberp in priority_integers and numberp not in user_priorities:
                user_priorities.append(numberp)
        else:
            print("Not an integer to represent the priority!")

    #TODO: yes, seconds is bad here
    print("Enter the free time in seconds:")
    user_free_time = 0
    while True:
        free_time = input()
        if re.match("\d+", free_time):
            user_free_time = float(free_time)
            break
        else:
            print("Not an integer to represent the free time!")

    all_possible_time_variants = []
    for up in user_priorities:
        show_serial_duration = time.strptime(all_interested[up][1],'%H:%M:%S')
        seconds = timedelta(hours = show_serial_duration.tm_hour, minutes = show_serial_duration.tm_min, seconds = show_serial_duration.tm_sec).total_seconds()
        all_possible_time_variants.append(seconds)

    #The goal is to follow the chosen priority and then "watch as much as possible".
    all_possible_max_variants = []
    all_possible_max_variants2 = []
    calculateSumVariants(all_possible_time_variants, user_free_time)
    max_length_of_variants = 0
    for apmv in all_possible_max_variants:
        if len(apmv) > max_length_of_variants:
            max_length_of_variants = len(apmv)
    if max_length_of_variants > 0:
        for mx in all_possible_max_variants:
            if len(mx) == max_length_of_variants:
                all_possible_max_variants2.append(mx)

    final_choices = []
    for priority in user_priorities:
        prioritized_selection = all_interested[priority]
        d = time.strptime(prioritized_selection[1],'%H:%M:%S')
        sd = timedelta(hours = d.tm_hour, minutes = d.tm_min, seconds = d.tm_sec).total_seconds()
        for apmv in all_possible_max_variants2:
            if sd in apmv:
                if user_free_time > sd:
                    final_choices.append(prioritized_selection[0])
                    user_free_time -= sd
                else:
                    break

    print("\nConsidering the time you have, you should watch these shows/serials today:\n")
    for fc in final_choices:
        print(fc)

main()

# Error bypass start logic for future.
"""
try:
    start()
    communication()
except:
    print("An error occurred...\nTrying again...\n")
    t.sleep(10)
    start()
    communication()
"""