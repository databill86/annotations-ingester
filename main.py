#!/usr/bin/python

from es_common import *
from nlp_service import *
from annotations_indexer import *

import logging
import argparse
import yaml


class AppConfig:
    """
    The configuration file for the indexer application
    """
    def __init__(self, file_path):
        """
        :param: filepath: the path for the configuration file stored in YAML
        """
        try:
            with open(file_path) as conf_file:
                yaml_file = yaml.safe_load(conf_file)

                if 'source' not in yaml_file or \
                        'nlp-service' not in yaml_file or \
                        'sink' not in yaml_file or \
                        'mapping' not in yaml_file:
                    raise Exception("Invalid configuration file provided")

                self.params = yaml_file

        except FileNotFoundError:
            raise Exception("Cannot open configuration file")


if __name__ == "__main__":
    # parse the input parameters
    parser = argparse.ArgumentParser(description='ElasticSearch-to-ElasticSearch annotations indexer')
    parser.add_argument('--config', help='configuration file path')
    args = parser.parse_args()

    if args.config is None:
        parser.print_usage()
        exit(0)

    # setup logging
    log_format = '[%(asctime)s] [%(levelname)s] %(name)s: %(message)s'
    logging.basicConfig(format=log_format, level=logging.INFO)

    try:
        config = AppConfig(args.config)

        # set up Elastic logger for the initialization time
        logging.getLogger('elasticsearch').setLevel(level=logging.ERROR)

        # initialize the elastic source
        source_params = config.params['source']
        es_source_conf = ElasticConnectorConfig(hosts=source_params['es']['hosts'])
        es_source_conn = ElasticConnector(es_source_conf)

        es_source = ElasticRangedIndexer(es_source_conn, source_params['es']['index-name'])

        # initialize NLP service
        nlp_service = BioyodieService(config.params['nlp-service']['endpoint-url'])

        # initialize the elastic sink
        sink_params = config.params['sink']
        es_sink_conf = ElasticConnectorConfig(hosts=sink_params['es']['hosts'])
        es_sink_conn = ElasticConnector(es_sink_conf)
        es_sink = ElasticIndexer(es_sink_conn, sink_params['es']['index-name'])

        # initialize the indexer
        mapping = config.params['mapping']
        indexer = BatchAnnotationsIndexer(nlp_service=nlp_service,
                                          source_indexer=es_source,
                                          source_text_field=mapping['source']['text-field'],
                                          source_docid_field=mapping['source']['docid-field'],
                                          source_fields_to_persist=mapping['source']['persist-fields'],
                                          split_index_by_field=mapping['sink']['split-index-by-field'],
                                          sink_indexer=es_sink,
                                          source_batch_date_field=mapping['source']['batch']['date-field'],
                                          batch_date_format=mapping['source']['batch']['date-format'])
    except Exception as e:
        log = logging.getLogger('main')
        log.error("Cannot initialize the application: " + str(e))
        exit(1)

    # set up the Elastic logger to be more verbose and run the indexer
    logging.getLogger('elasticsearch').setLevel(level=logging.WARN)
    
    indexer.index_range(batch_date_start=mapping['source']['batch']['date-start'],
                        batch_date_end=mapping['source']['batch']['date-end'])

