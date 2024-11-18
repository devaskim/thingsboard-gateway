#     Copyright 2024. ThingsBoard
#
#     Licensed under the Apache License, Version 2.0 (the "License");
#     you may not use this file except in compliance with the License.
#     You may obtain a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#     Unless required by applicable law or agreed to in writing, software
#     distributed under the License is distributed on an "AS IS" BASIS,
#     WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#     See the License for the specific language governing permissions and
#     limitations under the License.

from time import time

from thingsboard_gateway.gateway.entities.converted_data import ConvertedData
from thingsboard_gateway.gateway.entities.event_pack import EventPack
from thingsboard_gateway.storage.event_storage import EventStorage
from thingsboard_gateway.storage.sqlite.database import Database
from queue import Queue
from thingsboard_gateway.storage.sqlite.database_request import DatabaseRequest
from thingsboard_gateway.storage.sqlite.database_action_type import DatabaseActionType
#
#   No need to import DatabaseResponse, responses come to this component to be deconstructed
#
from logging import getLogger


class SQLiteEventStorage(EventStorage):
    """
    HIGH level api for thingsboard_gateway main loop
    """

    def __init__(self, config, logger):
        self.__log = logger
        self.__log.info("Sqlite Storage initializing...")
        self.__log.info("Initializing read and process queues")
        self.processQueue = Queue(-1)
        self.db = Database(config, self.processQueue, self.__log)
        self.db.setProcessQueue(self.processQueue)
        self.db.init_table()
        self.__log.info("Sqlite storage initialized!")
        self.delete_time_point = None
        self.last_read = time()
        self.stopped = False
        self.__event_data_pack = None

    def get_event_pack(self):
        if self.stopped:
            return EventPack()

        if self.__event_data_pack is None:
            self.__event_data_pack = EventPack()
            try:
                data_from_storage = self.read_data()

                timestamps = []
                for timestamp, data in data_from_storage:
                    timestamps.append(timestamp)
                    self.__event_data_pack.append(ConvertedData.deserialize(data))

                self.delete_time_point = max(timestamps) if timestamps else None
            except Exception:
                self.__event_data_pack = None
        return self.__event_data_pack

    def event_pack_processing_done(self):
        if not self.stopped:
            self.__event_data_pack = None
            self.delete_data(self.delete_time_point)

    def read_data(self):
        self.db.__stopped = True
        data = self.db.read_data()
        self.db.__stopped = False
        return data

    def delete_data(self, ts):
        return self.db.delete_data(ts)

    def put(self, message):
        try:
            if not self.stopped:
                _type = DatabaseActionType.WRITE_DATA_STORAGE
                request = DatabaseRequest(_type, message)

                self.__log.info("Sending data to storage")
                self.processQueue.put(request)
                return True
            else:
                return False
        except Exception as e:
            self.__log.exception("Failed to write data to storage! Error: %s", e)

    def stop(self):
        self.stopped = True
        self.db.__stopped = True
        self.db.closeDB()

    def len(self):
        return self.processQueue.qsize()

    def update_logger(self):
        self.__log = getLogger("storage")
