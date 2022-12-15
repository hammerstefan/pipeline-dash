from pipeline_dash.job_data import JobDataDict


def add_human_url_to_job_data(job_data: JobDataDict, translate_mapping: dict):
    """
    Add human_url key to each job_data entry which involves translating job_data[i].url using the
    `translate_mapping
    """
    for data in job_data.values():
        data.human_url = data.url
        if data.human_url is None:
            continue
        for source, target in translate_mapping.items():
            data.human_url = data.human_url.replace(source, target)
