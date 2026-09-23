# SPDX-FileCopyrightText: 2026 EACG GmbH
#
# SPDX-License-Identifier: Apache-2.0

"""
Client for the TrustSource API, modelled on ts-scan's ``ts_scan.api``.

Two deliberate differences from ts-scan's copy:

* **The API version lives in the base URL, never in the method paths.**
  ts-scan writes ``self._post('v2/core/scans', ...)``; here the default base URL
  is ``https://api.trustsource.io/v2`` and the path is ``core/imports/scan/obom``.
  A version bump is then one value in one place (and one ``--base-url`` away in
  CI) instead of an edit per call site.
* **Errors carry the status code and the platform's own messages.** The OBOM
  endpoint answers a rejected document with ``400`` and a ``messages`` list
  saying what was wrong with it; swallowing that into a bare string would hide
  exactly the information the caller needs.
"""

from __future__ import annotations

import json
import typing as t

from copy import copy
from pathlib import Path

import requests


class TrustSourceAPI:
    class Error(Exception):
        def __init__(self, text: str, status_code: t.Optional[int] = None):
            self.status_code = status_code
            self.messages: t.List[str] = []

            message = text
            try:
                data = json.loads(text)
            except Exception:
                data = None

            if isinstance(data, dict):
                self.messages = [str(m) for m in data.get('messages') or []]
                message = data.get('description') or data.get('message') or data.get('error') or text
            elif isinstance(data, str):
                message = data

            if status_code:
                message = f'{message} (HTTP {status_code})'

            super().__init__(message)

    def __init__(self, base_url: str, api_key: str):
        from . import __version__

        self.__base_url = base_url.rstrip('/')
        self.__headers = {
            'Content-Type': 'application/json',
            'user-agent': f'ts-obom/{__version__}',
            # Always a header, always this spelling -- never in the body or URL.
            'x-api-key': api_key,
        }

    def _post(self,
              path: str,
              headers: t.Optional[dict] = None,
              data: t.Optional[t.Any] = None,
              json_data: t.Optional[dict] = None,
              params: t.Optional[dict] = None) -> dict:

        _headers = copy(self.__headers)
        if headers:
            _headers.update(headers)

        resp = requests.post(f'{self.__base_url}/{path}',
                             json=json_data,
                             data=data,
                             headers=_headers,
                             params=params)

        if resp:
            return resp.json()

        raise TrustSourceAPI.Error(resp.text, status_code=resp.status_code)

    def _get(self, path: str,
             headers: t.Optional[dict] = None,
             params: t.Optional[dict] = None) -> dict:

        _headers = copy(self.__headers)
        if headers:
            _headers.update(headers)

        resp = requests.get(f'{self.__base_url}/{path}', headers=_headers, params=params)

        if resp:
            return resp.json()

        raise TrustSourceAPI.Error(resp.text, status_code=resp.status_code)

    def import_obom(self, obom_path: Path, params: dict) -> dict:
        """Stores a CycloneDX OBOM for a project or one of its modules.

        The document is sent as the raw request body; the scope (which project,
        which module) and the provenance (``toolName``/``toolVersion``) travel
        as query parameters, because that is how the endpoint resolves them --
        nothing inside the document decides where it lands.
        """
        with obom_path.open('r') as fp:
            return self._post('core/imports/scan/obom', data=fp.read().encode('utf-8'),
                              params=params)

    def read_obom(self, params: dict) -> dict:
        """Presence (``mode=presence``, the default) or the stored document
        (``mode=full``) for one scope."""
        return self._get('core/obom', params=params)
