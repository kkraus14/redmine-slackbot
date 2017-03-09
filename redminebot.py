import os
import time
from slackclient import SlackClient
from redmine import Redmine

# redminebot's ID and external host from environment variables
BOT_ID = os.environ.get('BOT_ID')
EXT_HOST = os.environ.get('REDMINE_EXT_HOST')

# constants
AT_BOT = "<@" + BOT_ID + ">"

# instantiate Slack & Redmine clients
sc = SlackClient(os.environ.get('BOT_TOKEN'))
rc = Redmine(os.environ.get('REDMINE_HOST'), version=os.environ.get('REDMINE_VERSION'), \
     key=os.environ.get('REDMINE_TOKEN'))

def handle_command(command, channel, username):
    """
        Receives commands directed at the bot and determines if they
        are valid commands. If so, then acts on the commands. If not,
        returns back what it needs for clarification.
    """
    response = ":question: Unknown/invalid command - Try `help` for a list of supported commands"
    commands = command.split()
    if commands:
        operator = commands[0]
        s = " "
        msg = s.join(commands[1:])
        if operator == "issueto" and len(commands) > 2:
            assigneduser = commands[1]
            newmsg = s.join(commands[2:])
            response = create_issue(newmsg, username, assigneduser)
        elif operator == "issue" and len(commands) > 1:
            response = create_issue(msg, username, username)
        elif operator == "close" and len(commands) > 2:
            issue = commands[1]
            newmsg = s.join(commands[2:])
            response = close_issue(newmsg, issue, username)
        elif operator == "list":
            response = list_issues(username)
        elif operator == "listfrom" and len(commands) > 1:
            listuser = commands[1]
            response = list_issues(listuser) 
        elif operator == "help":
            response = show_commands()
    message = "@" + username + " " + response
    sc.api_call("chat.postMessage", channel=channel, \
                          text=message, as_user=True)


def parse_slack_output(slack_rtm_output):
    """
        The Slack Real Time Messaging API is an events firehose.
        this parsing function returns None unless a message is
        directed at the Bot, based on its ID.
    """
    output_list = slack_rtm_output
    if output_list and len(output_list) > 0:
        for output in output_list:
            if output and 'text' in output and AT_BOT in output['text']:
                profile = sc.api_call("users.info", user=output['user'])
                username = profile['user']['name']
                # return text after the @ mention, whitespace removed
                return output['text'].split(AT_BOT)[1].strip().lower(), \
                       output['channel'], username
    return None, None, None

def show_commands():
    """
        Return ist of commands that bot can handle
    """
    return ":wrench: List of supported commands:\n" \
           "`issue <subject>` - creates new issue and assigns it to you\n" \
	   "`issueto <name> <subject>` - creates new issue and assigns it to `<name>`\n" \
           "`close <issue #> <comment>` - closes an issue with the following comment\n" \
           "`list` - list all open issues assigned to you\n" \
           "`listfrom <name>` - list all open issues assigned to `<name>`"

"""
    Redmine commands
"""
def get_user(username):
    users = rc.user.filter(name=username)
    if len(users) == 0:
        return None
    return users[0]

def list_issues(username):
    user = get_user(username)
    if not user:
        return ":x: Failed to find user `"+username+"` in Redmine"
    result = rc.issue.filter(sort='project', assigned_to_id=user.id, status_id='open')
    response = ""
    if len(result) > 0:
        response = ":book: Open issues assigned to "+user.firstname+" "+user.lastname+":\n"
        for issue in result:
            response += ""+issue.project.name+" <"+EXT_HOST+"/issues/"+str(issue.id)+"|#"+str(issue.id)+ \
                        " "+issue.subject+">\n"
    else:
        response = ":thumbsup_all: No open issues assigned to "+user.firstname+" "+user.lastname
    return response

def close_issue(text, issue, username):
    user = get_user(username)
    if not user:
        return ":x: Failed to find user `"+username+"` in Redmine"
    # impersonate user so it looks like the update is from them
    rcn = Redmine(os.environ.get('REDMINE_HOST'), version=os.environ.get('REDMINE_VERSION'), \
     key=os.environ.get('REDMINE_TOKEN'), impersonate=user.login)
    result = rcn.issue.update(issue, status_id=5, notes=text, done_ratio=100)
    if result:
        return ":white_check_mark: Closed Issue <"+EXT_HOST+"/issues/"+str(issue)+ \
        "|#"+str(issue)+">"
    else:
        return ":x: Issue closing failed"

def create_issue(text, username, assigneduser):
    user = get_user(username)
    if not user:
        return ":x: Failed to find user `"+username+"` in Redmine"
    assigned = get_user(assigneduser)
    if not assigned:
        return ":x: Failed to find user `"+assigneduser+"` in Redmine"
    # impersonate user so it looks like the update is from them
    rcn = Redmine(os.environ.get('REDMINE_HOST'), version=os.environ.get('REDMINE_VERSION'), \
     key=os.environ.get('REDMINE_TOKEN'), impersonate=user.login)
    issue = rcn.issue.create(project_id='general', subject=text, tracker_id=2, assigned_to_id=assigned.id)
    if issue.id:
        return ":white_check_mark: Created Issue <"+EXT_HOST+"/issues/"+str(issue.id)+ \
        "|#"+str(issue.id)+" "+issue.subject+"> assigned to "+assigned.firstname+" "+assigned.lastname
    else:
        return ":x: Issue creation failed"

if __name__ == "__main__":
    READ_WEBSOCKET_DELAY = 1 # 1 second delay between reading from firehose
    if sc.rtm_connect():
        print("RedmineBot connected and running!")
        while True:
            command, channel, username = parse_slack_output(sc.rtm_read())
            if command and channel and username:
                handle_command(command, channel, username)
            elif channel and username:
                handle_command("help", channel, username)
            time.sleep(READ_WEBSOCKET_DELAY)
    else:
        print("Connection failed. Invalid Slack token or bot ID?")