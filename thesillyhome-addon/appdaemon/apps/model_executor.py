import appdaemon.plugins.hass.hassapi as hass
import thesillyhome.model_creator.read_config_json as tsh_config
import pickle
import pandas as pd
from pandas import DataFrame
from sklearn.tree import DecisionTreeClassifier
from datetime import datetime
import copy
import os.path


class ModelExecutor(hass.Hass):
    def initialize(self):
        self.model_name_version = tsh_config.model_name_version
        self.act_model_set = self.load_models()
        self.handle = self.listen_state(self.state_handler)
        self.log("Hello from TheSillyHome")
        self.log("TheSillyHome has now started!")

    def load_models(self):
        actuators = tsh_config.actuators
        act_model_set = {}
        for act in actuators:
            if os.path.isfile(f"/data/model/{self.model_name_version}/{act}.pickle"):
                with open(
                    f"/data/model/{self.model_name_version}/{act}.pickle", "rb"
                ) as pickle_file:
                    content = pickle.load(pickle_file)
                    act_model_set[act] = content
                print(f"Loaded model for {act}")
            else:
                print(f"No model for {act}")
        return act_model_set

    def state_handler(self, entity, attribute, old, new, kwargs):
        sensors = tsh_config.sensors
        float_sensors = tsh_config.float_sensors

        if entity in sensors:
            self.log(f"{entity} is {new}")

            # Get feature list from parsed data header, set all columns to 0
            output_list = tsh_config.output_list
            feature_list = pd.read_csv("/data/act_states.csv", index=False).columns

            feature_list = sorted(list(set(feature_list) - set(output_list)))
            feature_list = pd.DataFrame(columns=feature_list)
            feature_list = feature_list.append(pd.Series(), ignore_index=True)
            feature_list.iloc[0] = 0

            # Get state of all sensors for model input
            df_sen_states = copy.deepcopy(feature_list)
            for sensor in sensors:
                true_state = self.get_state(entity_id=sensor)
                if sensor not in float_sensors:
                    if f"{sensor}_{true_state}" in df_sen_states.columns:
                        df_sen_states[sensor + "_" + true_state] = 1
                elif sensor in float_sensors:
                    if (true_state) in df_sen_states.columns:
                        df_sen_states[sensor] = true_state
            print(df_sen_states)
            print(len(df_sen_states.columns))

            # Execute all models for sensor and set states
            for act, model in self.act_model_set.items():
                cur_act_list = []
                for feature in list(df_sen_states.columns):
                    if feature.startswith(act):
                        cur_act_list.append(feature)
                df_sen_states = df_sen_states[
                    sorted(list(set(df_sen_states.columns) - set(cur_act_list)))
                ]

                prediction = model.predict(df_sen_states)[0].split("::")[1]
                if prediction == "on":
                    self.log(f"Turn on {act}")
                    self.turn_on(act)
                elif prediction == "off":
                    self.log(f"Turn off {act}")
                    self.turn_off(act)
