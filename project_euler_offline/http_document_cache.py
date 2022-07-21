#!/bin/env python

import datetime
import http
import json
import sqlite3

import aiohttp


class DataRetrievalError(BaseException):
    pass


class MissingDataError(DataRetrievalError):
    pass


class HttpDocumentCache:
    def __init__(self, database_file_path):
        self._database_file_path = database_file_path
        self._database_connection = self._setup_database(self._database_file_path)

    def _setup_database(self, database_file_path):
        database_file_path.parent.mkdir(parents=True, exist_ok=True)

        database_connection = sqlite3.connect(
            str(database_file_path), detect_types=sqlite3.PARSE_DECLTYPES
        )
        database_connection.row_factory = sqlite3.Row

        sqlite3.register_adapter(datetime.datetime, lambda value: value.isoformat())
        sqlite3.register_adapter(
            dict, lambda value: json.dumps(value, separators=(",", ":")).encode("utf8")
        )
        sqlite3.register_converter(
            "datetime",
            lambda data: datetime.datetime.fromisoformat(data.decode("utf8")),
        )
        sqlite3.register_converter(
            "dictionary", lambda data: json.loads(data.decode("utf8"))
        )

        with database_connection:
            database_connection.execute(
                """
                create table if not exists http_cache 
                (request_timestamp datetime, request_url text, request_headers dictionary, response_headers dictionary, response_data blob)
            """
            )

        return database_connection

    async def retrieve_data(
        self, request_url, cache_disable=False, cache_only=False, force=False
    ):
        if not cache_disable and not force:
            cache_entry = next(
                self._database_connection.execute(
                    "select * from http_cache where request_url=:request_url",
                    {"request_url": request_url},
                ),
                None,
            )

            if cache_entry is not None:
                if len(cache_entry["response_data"]) != 0:
                    return cache_entry["response_data"]

        if not cache_only:
            async with aiohttp.ClientSession() as session:
                request_timestamp = datetime.datetime.now()

                request_headers = {}

                async with session.get(
                    request_url, headers=request_headers
                ) as response:
                    if response.status == http.HTTPStatus.OK:
                        response_headers = {k: v for k, v in response.headers.items()}
                        response_data = await response.read()

                        if not response_data or len(response_data) == 0:
                            raise MissingDataError(
                                f"{request_url}: Missing response payload"
                            )

                        if not cache_disable:
                            with self._database_connection:
                                self._database_connection.execute(
                                    "insert into http_cache(request_timestamp, request_url, request_headers, response_headers, response_data) "
                                    + "values (:request_timestamp, :request_url, :request_headers, :response_headers, :response_data)",
                                    {
                                        "request_timestamp": request_timestamp,
                                        "request_url": request_url,
                                        "request_headers": request_headers,
                                        "response_headers": response_headers,
                                        "response_data": response_data,
                                    },
                                )

                        return response_data
                    elif response.status == http.HTTPStatus.FOUND:
                        raise MissingDataError(
                            f"{request_url}: HTTP 302 (Object moved temporarily)"
                        )
                    else:
                        raise DataRetrievalError(
                            f"{request_url}: HTTP {response.status}"
                        )
