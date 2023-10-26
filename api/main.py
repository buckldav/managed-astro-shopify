from fastapi import FastAPI, Body
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum

app = FastAPI()


@app.get("/")
def hello():
    return {"hi": "there"}


GITLAB_VARIABLE_TYPE = "env_var"


class EnvVarTarget(str, Enum):
    PRODUCTION = "production"
    PREVIEW = "preview"
    DEVELOPMENT = "development"


class EnvVarType(str, Enum):
    """
    Based on Vercel's type enum: https://vercel.com/docs/rest-api/endpoints#projects/create-one-or-more-environment-variables/body-parameters.
    Plain is just plaintext. Unsuitable for secrets.
    Secret is masked.
    Encrypted is masked and encrypted.
    """

    SECRET = "secret"
    ENCRYPTED = "encrypted"
    PLAIN = "plain"


class EnvVar(BaseModel):
    key: str
    value: str
    type: EnvVarType
    target: Optional[List[EnvVarTarget]] = Field(
        default=[
            EnvVarTarget.DEVELOPMENT,
            EnvVarTarget.PREVIEW,
            EnvVarTarget.PRODUCTION,
        ]
    )
    git_branch: Optional[str]
    description: Optional[str] = Field(
        description="vercel: comment; gitlab: description"
    )

    def masked(self):
        """
        For the GitLab API, hide the variable from logs.
        """
        return self.type != EnvVarType.PLAIN

    def protected(self):
        """
        For the GitLab API, only for a protected branch (e.g. default branch). If the only target for the variable is production, return true. Else false.
        """
        return len(self.target) == 1 and EnvVarTarget.PRODUCTION in self.target

    def environment_scope(self):
        """
        For the GitLab API. For now, just use the default of "*". Could potentially use git_branch to name environments.
        """
        return "*"

    def raw(self):
        """
        For the GitLab API.
        We aren't supporting variable expansion because vault and vercel don't.
        https://docs.gitlab.com/ee/ci/variables/index.html#prevent-cicd-variable-expansion
        """
        return True

    def to_vercel_dict(self):
        return {
            "key": self.key,
            "value": self.value,
            "type": self.type,
            "target": self.target,
            "gitBranch": self.git_branch,
            "comment": self.description,
        }

    def to_gitlab_dict(self):
        return {
            "key": self.key,
            "value": self.value,
            "variable_type": GITLAB_VARIABLE_TYPE,
            "protected": self.protected(),
            "masked": self.masked(),
            "raw": self.raw(),
            "environment_scope": self.environment_scope(),
            "description": self.description,
        }


@app.post("/env")
def create_env_var(body: EnvVar = Body(...)):
    """
    https://about.gitlab.com/blog/2021/04/09/demystifying-ci-cd-variables/
    https://docs.gitlab.com/ee/api/project_level_variables.html#create-a-variable
    https://vercel.com/docs/rest-api/endpoints#create-one-or-more-environment-variables
    """
