from pred_api import *
import json
import datetime
import pandas as pd
import numpy as np
from sklearn.metrics import mean_squared_error, mean_absolute_error


def metrics_func(pred_day, json_path):
    '''

    Parameters
    ----------
    pred_day: string - "%Y%m%d".
    json_path: the json file saving the prediction result.

    Returns None
    -------

    '''
    with open(json_path, 'w') as f:
        data = json.load(json_path)
    for building in data.keys():
        usage_pred = np.array(data[building])
        start_date = datetime.datetime.strptime(pred_day, "%Y%m%d")
        end_date = start_date + datetime.timedelta(days=7)
        df_electricity = pd.read_csv(f"../../data/electricity/{building}.csv")
        df_electricity['time'] = pd.to_datetime(df_electricity['time']) + datetime.timedelta(hours=8)

        mask_ele = (df_electricity['time'].dt.date >= start_date) & (df_electricity['time'].dt.date <= end_date)

        usage_y = df_electricity[mask_ele]['val'][1:]
        usage_y = np.array(usage_y)
        rmse = np.sqrt(mean_squared_error(usage_y, usage_pred))
        mape = np.mean(np.abs(usage_y - usage_pred) / usage_y)
        mae = mean_absolute_error(usage_y, usage_pred)

        return rmse, mape, mae


def main():
    model_path = "my_model/hidden=30-rnn_layer=2-context_day=30-min_lr=0.001.ckpt"
    pred_day = '20221124'  # 20221124
    num_day_context = 30
    result = predict_api(model_path, pred_day, num_day_context, crawl_forecast=True)
    print(result)
    # metrics_func(pred_day, json_path)
    # rmse, mape, mae = metrics_func(pred_day, json_path)
    # print(f"RMSE: {rmse}\nMAPE: {mape}\nMAE: {mae}")


if __name__ == "__main__":
    main()