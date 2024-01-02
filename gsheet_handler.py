from gspread import Client, Spreadsheet, Worksheet
from pandas import DataFrame
from api.socket.log import log_service


def create_spreadsheet(gc: Client, sheet_name: str) -> Spreadsheet:
    return gc.create(sheet_name)


def append_data_to_sheet(work_sheet: Worksheet, values: list):
    work_sheet.append_rows(values)


def write_to_gsheet(gc: Client, final_labeled_sheet: DataFrame, product_data: DataFrame, result_file: Spreadsheet):
    log_service.add_log('Writing results to Google Sheet ...')
    final_labeled_sheet.drop("key_words", axis=1, inplace=True)

    # write data to new file.
    result_sheet = gc.open_by_url(result_file.url)
    result_worksheet = result_sheet.get_worksheet(0)
    result_sheet.values_clear(f"A3:O{len(product_data)}")
    result_worksheet.update(f"A3:O{len(product_data)}", final_labeled_sheet.values.tolist())
    return result_file.url

def create_result_sheet(gc: Client, template_id: str, result_folder_id: str) -> Spreadsheet:
    log_service.add_log('Creating result sheet ...')
    # if there is a file has the same name => delete.
    try:
        exist_result = gc.open("Matching Result")
        gc.del_spreadsheet(exist_result.id)
    except:
        pass
    log_service.add_log('Done.')
    # Copy template to result file
    return gc.copy(file_id=template_id, title="Matching Result", folder_id=result_folder_id)
