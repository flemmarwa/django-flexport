# -*- coding: utf-8 -*-
import logging
import logging.config

def init_logger(instance='FlexportLogger'):
  path_file_conf = "/www/projects/pdz/dj/flexport/logging_flexport.conf"
  logging.config.fileConfig(path_file_conf) # SERVER BASEPATH
  logger_init = logging.getLogger(instance)
  return logger_init
