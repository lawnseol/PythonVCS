"""
Support gitea module.
"""

import requests
from requests import Response
from secrets import SystemRandom
import hashlib

class GiteaEmail:
    def __init__(self, email: str, primary: bool, verified: bool):
        """
        Gitea email properties.

        Args:
            email (str): Email address.
            primary (bool): Is primary email.
            verified (bool): Is verified email.
        """
        self.email: str = email
        self.primary: bool = primary
        self.verified: bool = verified

class GiteaAPIError(Exception):
    """raised when api does not success."""
    def __init__(self, raw_data: Response, response_status_code: int):
        super().__init__(f"GiteaAPIError with status code: {response_status_code}")
        self.raw_data = raw_data
        self.response_status_code = response_status_code

class WrongJSONError(Exception):
    """raised when JSON does not have right key."""
    def __init__(self, data: dict):
        super().__init__(f"Wrong json key: {data}")
        self.data = data

class Visibility:
    """Visibility for vaild visibility property."""
    public = "public"
    limited = "limited"
    private = "private"

class GiteaUser:
    """Class for find gitea user properties easily."""
    def __init__(self, response: Response):
        """
        Dict to gitea user properties.

        Args:
            response (Response): The /user response.

        Raises:
            WrongJSONError: When JSON is invaild.
        """
        responsejson: dict = response.json()
        self.active: bool = responsejson["active"]
        if self.active is None:
            raise WrongJSONError(responsejson)
        self.avatar_url: str = responsejson["avatar_url"]
        self.created_at: str = responsejson["created"]
        self.email: str = responsejson["email"]
        self.followers_count: int = responsejson["followers_count"]
        self.following_count: int = responsejson["following_count"]
        self.name: str = responsejson["full_name"]
        self.id: int = responsejson["id"]
        self.is_admin: bool = responsejson["is_admin"]
        self.language: str = responsejson["language"]
        self.last_login: str = responsejson["last_login"]
        self.location: str = responsejson["location"]
        self.username: str = responsejson["login"]
        self.prohibit_login: bool = responsejson["prohibit_login"]
        self.restricted: bool = responsejson["restricted"]
        self.starred_count: int = responsejson["starred_repos_count"]
        self.visibility: str = self.string_to_visibility(responsejson["visibility"])
        self.website: str = responsejson["website"]

    @staticmethod
    def string_to_visibility(string: str) -> Visibility or None: # type: ignore
        """Check visibility.
        Args:
            string (str): String that will be checked.

        Returns:
            str or None: if visibility is vaild, return visibility class. else, return None
        """
        if string == "public":
            return Visibility.public
        elif string == "private":
            return Visibility.private
        elif string == "limited":
            return Visibility.limited
        else:
            return None

class GiteaHandler:
    """Handler for gitea."""
    def __init__(self, name: str, password: str or None, url: str, token: str or None = None, cleanup: bool = True):    # type: ignore
        """
        Generate gitea handler.

        Args:
            name (str): The name of gitea user.
            password (str or None): The password of gitea user. Need for cleanup and token generation.
            url (str): The url of gitea.
            token (str or None, optional): Token for gitea. Defaults to None.
            cleanup (bool, optional): Cleanup token that giteahandler made. Defaults to True.

        Raises:
            ValueError: When token and password is None or password is None and cleanup is True.
            GiteaAPIError: When gitea api status code does not 201(success).
        """
        if (token is None and password is None) or password is None and cleanup:
            raise ValueError("not right parameter.")
        self.name = name
        self.url = url
        if self.url.endswith('/'):
            self.url = self.url.removesuffix('/')
        self.url = f'{self.url}/api/v1'
        if token is None and password is not None:
            responseget: Response = requests.get(f"{self.url}/users/{self.name}/tokens", auth=(self.name, password))
            if cleanup:
                for i in responseget.json():
                    namea: str = i["name"]
                    if namea.startswith("gitea-pythonvcs-"):
                        requests.delete(f"{self.url}/users/{self.name}/tokens/{namea}", auth=(self.name, password))
            data: dict[str, str] = {
                "name": "gitea-pythonvcs-" + random_key()
            }
            response: Response = requests.post(f"{self.url}/users/{self.name}/tokens", auth=(self.name, password), data=data)
            if response.status_code != 201:
                raise GiteaAPIError(response, response.status_code)
            else:
                self.token: str = response.json()["sha1"]
        else:
            self.token = token
        self.defaultheader: dict[str, str] = {
            "accept": "application/json",
            "Authorization": f'token {self.token}',
        }
        self.defaultparam: dict[str, str] = {"token": self.token}
        self.user = GiteaUser(requests.get(f"{self.url}/user", headers=self.defaultheader))

    def get_emails(self) -> list[GiteaEmail]:
        """Get emails of token owner.

        Returns:
            list[GiteaEmail]: Emails of token owner.
        """
        emails = requests.get(f"{self.url}/user/emails", params=self.defaultparam).json()
        return [GiteaEmail(i["email"], i["primary"], i["verified"]) for i in emails]

    def add_emails(self, emails: list[str]) -> list[GiteaEmail]:
        """Add emails to token owner.

        Args:
            emails (list[str]): Emails that will be added.

        Raises:
            GiteaAPIError: When gitea api status code does not 201(success).

        Returns:
            list[GiteaEmail]: Emails that was added.
        """
        emailresponse = requests.post(f"{self.url}/user/emails", data={"emails": emails}, params=self.defaultparam)
        if emailresponse.status_code != 201:
            raise GiteaAPIError(emailresponse, emailresponse.status_code)
        return [
            GiteaEmail(i["email"], i["primary"], i["verified"])
            for i in emailresponse.json()
        ]

    def remove_emails(self, emails: list[str]):
        """Remove emails from token owner.

        Args:
            emails (list[str]): Emails that will be removed.

        Raises:
            GiteaAPIError: When gitea api status code does not 204(success).
        """
        emailresponse = requests.delete(f"{self.url}/user/emails", json={"emails": emails}, params=self.defaultparam, headers=self.defaultheader)
        if emailresponse.status_code != 204:
            raise GiteaAPIError(emailresponse, emailresponse.status_code)

def random_key() -> str:
    """Random key for secure random."""
    return hashlib.sha3_512(str(SystemRandom().randint(1, 10000000)).encode('utf-8')).hexdigest()
