import os.path
import sys

from prediction_api import prediction_api
import datetime
import numpy as np
from sklearn.metrics import mean_squared_error, mean_absolute_error
import logging
import matplotlib.pyplot as plt


def test(model_name, task_name, prediction_len, rollback: bool):
    '''
    Test the performance of model on the test data set from 20210315 - 20210430
    Parameters
    ----------
    model_name: The name of model, str.
    Returns
    -------

    '''
    # select the ".ckpt" file path under the folder f"../data/train_recorder/{model_name}"
    train_recorder_folder = f"../data/train/{task_name}/{model_name}"
    model_path = os.path.join(train_recorder_folder,
                              [name for name in os.listdir(train_recorder_folder) if
                               name.endswith(".ckpt")][0])
    # data prediction for building 1A.
    buildings = ['1A', '1B', '1C', '1D', '1E', '2A', '2B', '2C', '2D', '2E']

    # 20221101 - 20230301
    pred_date_start = datetime.datetime.strptime("20221101", "%Y%m%d")

    # pred_date_end = datetime.datetime.strptime("20221102", "%Y%m%d")
    pred_date_end = datetime.datetime.strptime("20221201", "%Y%m%d")

    # create a datetime list from pred_date_start to pred_date_end
    pred_date_list = [pred_date_start + datetime.timedelta(days=i) for i in
                      range((pred_date_end - pred_date_start).days + 1)]

    logging.basicConfig(filename=f"test.log",
                        level=logging.INFO)
    # Input string
    input_str = model_name
    # Splitting the string by the delimiter "-"
    input_list = input_str.split("-")

    # Initializing the variable to store the context_day value
    context_len = None

    # Looping through the split list to find the context_day value
    for item in input_list:
        if "context_day" in item:
            context_len = int(item.split("=")[1])
            break

    logger = logging.getLogger(f"Metrics for the model {model_name}:\n")
    logger.info(context_len)
    logger.critical(f"context length: {context_len}\n")

    metrics_mat = np.zeros((len(buildings), 3))  # record the metrics of each building.
    test_y = np.zeros((len(buildings), len(pred_date_list), 24 * prediction_len))
    test_pred = np.zeros((len(buildings), len(pred_date_list), 24 * prediction_len))
    prediction = prediction_api()
    for i in range(len(pred_date_list)):
        pred_date = pred_date_list[i]
        # print(pred_date)
        pred_day = pred_date.strftime("%Y%m%d")

        context_end_date = pred_date - datetime.timedelta(days=1)
        context_end_date = context_end_date.strftime("%Y%m%d")
        prediction_result, original_buildings = prediction.custom_prediction(model_path, pred_day, context_end_date,
                                                                             context_len,
                                                                             prediction_len, rollback=rollback)
        # set the logger name as "metrics"
        # start_date = datetime.datetime.strptime(pred_day, "%Y%m%d")
        # end_date = start_date + datetime.timedelta(days=prediction_len - 1)
        for idx in range(len(buildings)):
            building = buildings[idx]
            usage_y = np.array(original_buildings[building])
            usage_pred = np.array(prediction_result[building])
            test_y[idx, i, :] = usage_y
            test_pred[idx, i, :] = usage_pred

        for idx in range(len(buildings)):
            # flatten the last two dimension
            building_test_y = test_y[idx, :, :].flatten()
            building_test_pred = test_pred[idx, :, :].flatten()
            # calculate the RMSE, MAPE, MAE
            # print(buildings[idx])
            # print(building_test_y)
            # print("\n\n")
            # print(building_test_pred)
            rmse = np.sqrt(mean_squared_error(building_test_y, building_test_pred))
            mape = np.mean(np.abs((building_test_y - building_test_pred) / building_test_y)) * 100
            mae = mean_absolute_error(building_test_y, building_test_pred)
            metrics_mat[idx, :] = [rmse, mape, mae]

        # draw the graph of the RMSE, MAPE, MAE for 10 buildings
        metrics_list = ["RMSE", "MAPE", "MAE"]
        task_save_path = f"../data/test/{task_name}"
        if not os.path.exists(task_save_path):
            os.makedirs(task_save_path)

        test_folder_path = f"../data/test/{task_name}/{model_name}"
        if not os.path.exists(test_folder_path):
            os.makedirs(test_folder_path)

        # draw the graph for each metrics on 10 buildings
        for m in range(len(metrics_list)):
            plt.figure()
            plt.plot(buildings, metrics_mat[:, m], label=metrics_list[m])
            # show the data point on the graph
            for b_i in range(len(buildings)):
                plt.scatter(b_i, metrics_mat[b_i, m], c="black")
                plt.annotate(metrics_mat[b_i, m], (b_i, metrics_mat[b_i, m]))
            # set the title, xlabel, ylabel, legend, grid
            plt.title(f"{metrics_list[m]}")
            plt.xlabel("Prediction Day")
            plt.ylabel("Value")
            plt.legend()
            plt.grid()
            plt.savefig(f"{test_folder_path}/{metrics_list[m]}.png")


if __name__ == "__main__":
    model_name = sys.argv[1]
    task_name = sys.argv[2]
    prediction_len = sys.argv[3]
    test(model_name, task_name, int(prediction_len))
