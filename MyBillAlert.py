import json
import requests
import datetime
import operator

url = "http://api119525live.gateway.akana.com:80/"
trans_url = "https://api119622live.gateway.akana.com:443/"
#response = requests.get(url + "users")
#json_data = json.loads(response.text)
#users = json_data["LegalParticipantIdentifierList"]

def found_dict((key, value), myList):
    for mydict in myList:
        if mydict[key] == value:
            return mydict
    return {}

def getUserAccounts(user):
    get_user_accounts = requests.post( url + "user/accounts" , json = user)
    user_accounts = json.loads(get_user_accounts.text)
    user_accounts = user_accounts["AccessibleAccountDetailList"]
    return user_accounts

def getUserAccountsInfo(user_accounts):
    info_List = []
    distinct_primary_id = []
    for info in user_accounts:
        op_id = info["OperatingCompanyIdentifier"].encode("utf-8")
        product_code = info["ProductCode"].encode("utf-8")
        primary_id = info["PrimaryIdentifier"].encode("utf-8")

        if ((product_code == 'CCD' or product_code == 'DDA') and primary_id not in distinct_primary_id):
            distinct_primary_id.append(primary_id)
            info_dict = {"OperatingCompanyIdentifier" : op_id, "ProductCode" : product_code, "PrimaryIdentifier" : primary_id}
            info_List.append(info_dict)
    return info_List

def getTransactions(accounts_info):
    for info_dict in accounts_info:
        info_dict = json.dumps(info_dict)
        get_transactions = requests.post( trans_url + "account/transactions", info_dict)
        #print(get_transactions.status_code)
        transactions = json.loads(get_transactions.text)
        all_transactions = transactions["MonetaryTransactionResponseList"]
    return all_transactions

def processTransactions(user, transactions):
    epoch = datetime.datetime(1970, 1, 1)
    user_accounts = getUserAccounts(user)
    accounts_info = getUserAccountsInfo(user_accounts)
    user_trans_history = []
    product_code_list = []

    for account in accounts_info:
        product_code = account["ProductCode"].encode("utf-8")
        product_code_list.append(product_code)

    for transaction in transactions:
        for product_code in product_code_list:

            if (product_code == 'CCD'):
                if ("TransactionDescription" in transaction and "TransactionSource" in transaction ):
                    description = transaction["TransactionDescription"].encode("utf-8").upper()
                    amount = transaction["PostedAmount"].encode("utf-8").upper()
                    trans_type = transaction["TransactionSource"].encode("utf-8").upper()
                    trans_time = transaction["TransactionDateTime"]
                    epoch_trans_time = int((datetime.datetime.strptime(trans_time, "%Y-%m-%dT%H:%M:%S.%f") - epoch).total_seconds())
                    trans_date = trans_time[0:10]

            if (product_code == 'DDA'):
                if ("Description1" in transaction):
                    description = transaction["Description1"].encode("utf-8").upper()
                trans_type = transaction["TransactionLevelCode"].encode("utf-8").upper()
                amount = transaction["PostedAmount"].encode("utf-8").upper()
                trans_date = transaction["EffectiveDate"]
                trans_time = transaction["TransactionTime"]
                trans_datetime = trans_date + 'T' + trans_time
                epoch_trans_time = int((datetime.datetime.strptime(trans_datetime, "%Y-%m-%dT%H:%M:%S") - epoch).total_seconds())
            # output only necessary user records
        trans_record = {'type' : trans_type, 'description' : description, 'amount' : amount, 'time' : epoch_trans_time * 1000, 'product_code' : product_code, 'date': trans_date}
        user_trans_history.append(trans_record)

    user_trans_history = [dict(t) for t in set([tuple(d.items()) for d in user_trans_history])] # remove duplicate records
    # test data:
    test_record1 = {'type' : "PAYMENT", 'description' : "OVERDRAFT FEE", 'amount' : "100.0", 'time' : 1469145612000, 'product_code' : "DDA", 'date' : '2016-07-22'}
    test_record2 = {'type' : "PAYMENT", 'description' : "OVERDRAFT FEE", 'amount' : "180.0", 'time' : 1468887746000, 'product_code' : "DDA", 'date' : '2016-07-19'}
    user_trans_history.append(test_record1)
    user_trans_history.append(test_record2)

    return user_trans_history

def findSuspects(user, transactions):
    L15_DAYS = 86400000 * 15
    L28_DAYS = 86400000 * 28
    TYPES = ["WITHDRAWAL", "FEE", "PAYMENT", "BILLED"]
    DANGER_SIGNALS = ["OVERDRAFT", "HEALTH", "INTEREST", "CHARGE", "INC"]
    user_trans_history = processTransactions(user, transactions)

    for idx, record in enumerate(user_trans_history):
        amount = record["amount"]
        time = record["time"]
        description = record["description"]
        date = record["date"]
        trans_type = record["type"]
        # find records with the same description
        dup_des = found_dict(('description', description), user_trans_history)
        # conditions
        des_cond = user_trans_history.index(dup_des) != idx
        time_cond = abs(time - dup_des["time"]) <= L28_DAYS or abs(time - dup_des["time"]) <= L15_DAYS
        type_cond = True if trans_type in TYPES else False
        sig_cond = True if description in DANGER_SIGNALS else False

        if (des_cond and time_cond and (type_cond or sig_cond)):
            if (dup_des["time"] > time):
                dup_des, record = record, dup_des
            curr_alert = "$" + str(amount) + " paid to " + description + " on " + str(date)
            past_alert = "$" + str(dup_des["amount"]) + " was also paid to " + str(dup_des["description"]) + " on " + str(dup_des["date"])
            alert = 'ALERT' + '\n' + curr_alert + '\n' + past_alert + '\n'
            print(alert)
            user_answer = raw_input("Is this intended? Y/N :")
            user_answer = user_answer.upper()
            if user_answer != 'Y' and user_answer != 'N':
                user_answer = raw_input('Please answer Y or N: ')
                user_answer = user_answer.upper()
                continue
            elif user_answer == 'Y':
                return('Alert ignored')
            else:
                return('Sorry.')
    return 'No suspicious activities'

def main():
    user = {'LegalParticipantIdentifier': '908997180284469041'}
    user_accounts = getUserAccounts(user)
    user_accounts_info = getUserAccountsInfo(user_accounts)
    transactions = getTransactions(user_accounts_info)
    process_transactions = processTransactions(user, transactions)
    suspects = findSuspects(user, transactions)
    print(suspects)
main()
