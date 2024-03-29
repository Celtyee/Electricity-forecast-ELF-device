import datetime
import pandas as pd
import os
import json
from utils import dataset_generator, my_deepAR_model
from wunderground_crawler.utils import visualcrossing_crawler


class prediction_api:
    def __init__(self):
        self.input_path = "../data/input"
        self.output_path = "../data/output"
        if not os.path.exists(self.input_path):
            os.mkdir(self.input_path)
        if not os.path.exists(self.output_path):
            os.mkdir(self.output_path)

    def lastest_prediction(self, model_path, context_len) -> dict:
        '''
        forecast the electricity load from [pred_day, pred_day+num_day_pred). Save the prediction in ./prediction.json.
        The function will crawl data from google forecast website.

        Parameters
        -------
        model_path: pytorch checkpoint for training, e.g. "./model/model_epoch_10.ckpt"
        context_len: context_length

        Returns
        -------
        '''

        prediction_len = 7
        buildings = ['1A', '1B', '1C', '1D', '1E', '2A', '2B', '2C', '2D', '2E']

        pred_date_start = datetime.datetime.now().date()
        # debug for the date 2021-03-15

        pred_date_end = pred_date_start + datetime.timedelta(days=prediction_len - 1)

        hist_date_start = pred_date_start - datetime.timedelta(days=context_len + prediction_len + 1)
        hist_date_end = pred_date_start - datetime.timedelta(days=1)
        #
        print(f'forecast date {pred_date_start} - {pred_date_end}')
        print(f'context date {hist_date_start} - {hist_date_end}')

        electricity_path = "../data/electricity"
        future_weather_path = "../data/weather/future"
        vc = visualcrossing_crawler()
        prediction_weather_csv = f'{future_weather_path}/future_weather_{pred_date_start}_{pred_date_end}.csv'
        if not os.path.exists(prediction_weather_csv):
            vc.crawl_forecast(pred_date_start, pred_date_end, prediction_weather_csv)
        future_generator = dataset_generator(future_weather_path, electricity_path)

        # # compress the future data. The data will be saved in future_weather_path/future_weather.csv
        # future_generator.compress_weather_data(pred_weather_csv)
        pred_df_list = future_generator.generate_dataset(buildings, pred_date_start, pred_date_end,
                                                         prediction_weather_csv,
                                                         start_idx=1, weather_stride=1)

        # get historical whether data and electricity data
        context_weather_path = "../data/weather/history"

        context_weather_csv = f'{context_weather_path}/history_weather_vc.csv'
        context_generator = dataset_generator(context_weather_path, electricity_path)

        hist_df_list = context_generator.generate_dataset(buildings, hist_date_start, hist_date_end,
                                                          context_weather_csv, start_idx=1, weather_stride=1)

        # combine historical data and forecast weather data together as the condition data
        total_df_list = []
        for i in range(len(buildings)):
            pred_df_list[i]['val'] = 0
            df = pd.concat((hist_df_list[i], pred_df_list[i]), axis=0)
            df['time_idx'] = range(len(df))
            total_df_list.append(df)
        input_data = pd.concat(total_df_list)
        input_data.fillna(0, inplace=True)
        input_data_path = f'{self.input_path}/latest_input_data.csv'
        input_data.to_csv(input_data_path, index=False)

        # run prediction
        # print(f' read csv file from {pred_data_path}')
        model = my_deepAR_model(model_path, 24 * context_len, 24 * prediction_len, buildings)
        prediction = model.rollback_predict(input_data_path)

        prediction_path = "./prediction.json"
        with open(prediction_path, "w") as f:
            json.dump(prediction, f)

        print("Prediction finishes")
        return prediction

    def custom_prediction(self, model_path, pred_date, context_end, context_len, prediction_len=7,
                          buildings=None, rollback=False) -> (dict, dict):
        '''
        allow users to use custom weather as the input data for the prediction of the start day.
        The prediction result is stored in the file history_prediction.json.

        Parameters
        -------
        model_path: the path of pytorch checkpoint file, str: %Y%m%d.
        pred_date: the start date of prediction,  str. The pred_date should be one week ago from today.
        context_end: the end date of custom input weather, str: %Y%m%d.

        Returns
        -------
        prediction: the prediction result of custom context weather condition data, dict.
        '''
        # generate the input dataset

        if buildings is None:
            buildings = ['1A', '1B', '1C', '1D', '1E', '2A', '2B', '2C', '2D', '2E']
        pred_date_start = datetime.datetime.strptime(pred_date, "%Y%m%d").date()
        pred_date_end = pred_date_start + datetime.timedelta(days=prediction_len - 1)

        hist_date_end = datetime.datetime.strptime(context_end, "%Y%m%d").date()
        hist_date_start = (hist_date_end - datetime.timedelta(days=context_len + prediction_len - 1))

        print(f'forecast date {pred_date_start} - {pred_date_end}')
        print(f'context date {hist_date_start} - {hist_date_end}')

        context_weather = "../data/weather/history"
        electricity_path = "../data/electricity"
        context_weather_csv = f'{context_weather}/history_weather_vc.csv'
        context_generator = dataset_generator(context_weather, electricity_path)

        context_df_list = context_generator.generate_dataset(buildings, hist_date_start, hist_date_end,
                                                             context_weather_csv, start_idx=1, weather_stride=1)

        prediction_df_list = context_generator.generate_dataset(buildings, pred_date_start, pred_date_end,
                                                                context_weather_csv, start_idx=1, weather_stride=1)

        # combine historical data and forecast weather data together as the input data
        input_df_list = []
        for i in range(len(buildings)):
            prediction_df_list[i]['val'] = 0
            df = pd.concat((context_df_list[i], prediction_df_list[i]), axis=0)
            df['time_idx'] = range(len(df))
            input_df_list.append(df)
        input_df = pd.concat(input_df_list)

        input_data = f'{self.input_path}/input_data-pred_date={pred_date}-weather_start={hist_date_start}.csv'
        input_df.to_csv(input_data, index=False)
        # run prediction
        model = my_deepAR_model(model_path, 24 * context_len, 24 * prediction_len, buildings)
        if not rollback:
            prediction = model.predict(input_data)
        else:
            prediction = model.rollback_predict(input_data)

        # print("Prediction finishes")
        # fetch the original data
        original_usage = {}
        test_date_start = datetime.datetime.strptime(context_end, "%Y%m%d").date() + datetime.timedelta(days=1)
        test_date_end = test_date_start + datetime.timedelta(days=prediction_len - 1)
        for idx in range(len(buildings)):
            building = buildings[idx]
            building_path = f"../data/electricity/{building}_complete.csv"
            df_electricity = pd.read_csv(building_path)
            df_electricity['time'] = pd.to_datetime(df_electricity['time']) + datetime.timedelta(hours=7)

            mask_electricity = (df_electricity['time'].dt.date >= test_date_start) & (
                    df_electricity['time'].dt.date <= test_date_end)
            df_electricity = df_electricity.loc[mask_electricity]
            # set the 'val' column of the dataframe to nan if it is less or equal to 0
            original_usage[building] = df_electricity['val'].values.tolist()

        origin_path = f"{self.output_path}/origin-pred_date={pred_date}.json"
        with open(origin_path, "w") as f:
            json.dump(original_usage, f)

        prediction_path = f"{self.output_path}/prediction-pred_date={pred_date}.json"
        with open(prediction_path, "w") as f:
            json.dump(prediction, f)

        return prediction, original_usage


def unit_test():
    predictor = prediction_api()
    model_path = "./my_model/hidden=38-rnn_layer=3-context_day=3-min_lr=0.001.ckpt"
    prediction_date_start = datetime.datetime.strptime("20230302", "%Y%m%d")
    context_len = 3
    context_end_date = prediction_date_start - datetime.timedelta(days=1)
    context_end_date = context_end_date.strftime("%Y%m%d")
    prediction_date_start = prediction_date_start.strftime("%Y%m%d")
    predictor.custom_prediction(model_path, prediction_date_start, context_end_date, context_len, prediction_len=7)


if __name__ == "__main__":
    unit_test()
    pass
