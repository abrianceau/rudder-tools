# trick to make fake import compatible with regular import
if 'Config' not in vars():
  from common import *  
    
Config.REDMINE_ALT_API_URL = "https://redmine.normation.com"
Config.REDMINE_API_URL = "https://www.rudder-project.org/redmine"
Config.REDMINE_API_LIMIT = 100
Config.REDMINE_CLOSED_STATUSES = [5, 6, 16, 11] # 5=Released, 6=rejected, 16=resolved, 11=Pending release
Config.REDMINE_META_TRACKERS = [3]
Config.ACCESS_ROLE_LIST = [ 3, 4, 5, 6, 7, 8, 9, 11 ] # 7=Product owner, 3=Scrum master, 8=Lead developer, 4=Developer, 5=Reporter, 11=Release manager, 6=Consultant, 9=Integrator

# Keeping old version for reference
#TRACKER_NAME_MAPPING = { 'Bug': 'bug', 'Implementation (development)': 'dev', 'Implementation (integration)': 'int' }
Config.TRACKER_NAME_MAPPING = { 'Bug': 'bug', 'User story': 'ust', 'Architecture': 'arch', 'Change': 'chg', 'Problem': 'pbm', 'Incident': 'inc' }
Config.PENDING_TR_CODE = 3
Config.IN_PROGRESS_CODE = 9
Config.CUSTOM_FIELD_PR = 3
Config.ALT_CUSTOM_FIELD_PR = 1
Config.BUG_TACKER_ID = 1

class Issue:
  """Class to hold informations about a single issue"""
  def __init__(self, name, must_be_open=True):
    """name is a string like: 1234 or i1234"""
    self.name = name
    self.must_be_open = must_be_open
    self.info = None
    if name.startswith('#'):
      name = name [1:]
    is_internal = re.match(r'i(\d+)', name)
    if is_internal:
      self.id = int(is_internal.group(1))
      self.token = Config.REDMINE_ALT_TOKEN
      self.api_url = Config.REDMINE_ALT_API_URL
      self.custom_field_pr = Config.ALT_CUSTOM_FIELD_PR
      self.internal = True
    else:
      self.id = int(name)
      self.token = Config.REDMINE_TOKEN
      self.api_url = Config.REDMINE_API_URL
      self.custom_field_pr = Config.CUSTOM_FIELD_PR
      self.internal = False

  def __getitem__(self, key):
    """Make Issue behave like a dict"""
    self._get_info()
    if key not in self.info:
      return None
    return self.info[key]

  def __contains__(self, key):
    """Make Issue behave like a dict"""
    self._get_info()
    return key in self.info

  def _get_info(self):
    """Get issue informations from redmine"""
    if self.info is not None:
      return self.info
    # Find issue in redmine
    print("Looking for Redmine ticket #" + self.name + "... ", end=' ')
    sys.stdout.flush() # to display previous unfinished line
    issues_req = requests.get(self.api_url + "/issues/" + str(self.id) + ".json?include=journals",
                              headers = {'X-Redmine-API-Key': self.token, 'Content-Type': 'application/json' })
    issue = issues_req.json()['issue'] if issues_req.status_code == requests.codes.ok else None
    if not issue:
      print("Not found!")
      logfail("***** ERROR: ticket not found. Exiting.")
      if not Config.force:
        exit(2)
    else:
      print("Done")

    # Check ticket type
    if issue['tracker'] in Config.REDMINE_META_TRACKERS:
      print("This is a question ticket! You cannot make a pull request on this ticket.")
      logfail("***** ERROR: This is a question ticket. Exiting.")
      if not Config.force:
        exit(2)

    # Check ticket status
    if self.must_be_open and issue['status']['id'] in Config.REDMINE_CLOSED_STATUSES:
      print("This ticket is closed! You cannot make a pull request on this ticket.")
      logfail("***** ERROR: Closed ticket. Exiting.")
      if not Config.force:
        exit(2)

    if 'fixed_version' not in issue:
      print("This ticket has no target version! I can't make a branch against its repository.")
      logfail("***** ERROR: Missing target version. Exiting.")
      if not Config.force:
        exit(2)

    self.data = issue

    # Get ticket elements
    info = {}
    info['type'] = issue['tracker']['name']
    info['name'] = issue['subject']
    info['version'] = get_version(issue)
    info['project_id'] = issue['project']['id']
    info['tracker_id'] = issue['tracker']['id']
    info['priority_id'] = issue['priority']['id']
    info['subject'] = issue['subject']
    info['description'] = issue['description']
    info['private'] = 'is_private' in issue and issue['is_private']
    if 'category' in issue:
      info['category_id'] = issue['category']['id']
    if 'is_private' in issue:
      info['is_private'] = issue['is_private']
    if 'custom_fields' in issue:
      for field in issue['custom_fields']:
        if field['id'] == self.custom_field_pr and 'value' in field:
          info['pr'] = field['value']

    # Get ticket's last assignment besides me
    my_id = get_redmine_uid()
    if 'journals' in issue:
      for journal in issue['journals']:
        if 'details' in journal:
          for detail in journal['details']:
            if detail['name'] == 'assigned_to_id' and 'old_value' in detail:
              if int(detail['old_value']) != my_id:
                info['last_assignee'] = int(detail['old_value'])

    self.info = info
    return info

  def branch_name(self):
    """Create a branch name base on this issue"""
    branchified_name = re.sub("__+", "_", re.sub("[^" + string.ascii_letters + string.digits + "]", "_", self['name'].strip().lower())).strip("_")
    if self.internal:
      id = 'i' + str(self.id)
    else:
      id = str(self.id)
    if info['private']:
      branch_name = Config.TRACKER_NAME_MAPPING[self['type']] + "_" + id + "/_"
    else:
      branch_name = Config.TRACKER_NAME_MAPPING[self['type']] + "_" + id + "/" + branchified_name
    return branch_name

def issue_from_branch(branch):
  """Create issue object from given branch"""
  match = re.match(r'[A-Za-z]+_(i?\d+)/.*', branch)
  if match:
    return Issue(match.group(1))
  else:
    logfail("***** ERROR: This is not a ticket branch: " + branch)
    exit(4)

