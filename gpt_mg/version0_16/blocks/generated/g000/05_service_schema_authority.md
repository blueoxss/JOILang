- authoritative service schema snippet:
{
  "snippet_source": "service_schema_fallback",
  "canonical_rule": "Resolve schema matches against canonical_name. In final JOILang code, receiver tags after # must be uppercase-first title/Camel case, schema category tags must match the schema CamelCase, and the member token after ). or all(...). must be lowercase. For example, #bedroom #temperaturesensor becomes #Bedroom #TemperatureSensor and Switch_On becomes switch_on.",
  "binding_rule": [
    "Each device_group is one connected-device group or one schema fallback group.",
    "Each capability_binding pairs one category with the full authoritative service list for that category.",
    "user_defined_tags come from tags after removing category duplicates.",
    "locations are additional selector tags that can also be combined with the category.",
    "selector_tags are the usable extra tags that may be prepended before the category in a receiver.",
    "If the command does not mention any selector tag, the base receiver (#Category) is valid.",
    "If the command mentions locations or custom tags, preserve only the relevant selector tags before the category."
  ],
  "device_groups": [
    {
      "group_id": "schema::AirConditioner",
      "source": "service_schema_fallback",
      "categories": [
        "AirConditioner"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "AirConditioner",
          "category_tag": "#AirConditioner",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#AirConditioner)",
            "all(#AirConditioner)"
          ],
          "services": [
            {
              "service": "AirConditionerMode",
              "canonical_name": "AirConditioner_AirConditionerMode",
              "canonical_name_lower": "airconditioner_airconditionermode",
              "type": "value",
              "return_type": "ENUM",
              "return_descriptor": "Current air conditioner mode",
              "descriptor": "Controls air conditioner mode and temperature settings",
              "enums": [
                "auto",
                "cool",
                "heat"
              ]
            },
            {
              "service": "SetAirConditionerMode",
              "canonical_name": "AirConditioner_SetAirConditionerMode",
              "canonical_name_lower": "airconditioner_setairconditionermode",
              "type": "function",
              "argument_type": "ENUM",
              "argument_bounds": "Air conditioner mode to set",
              "argument_descriptor": "Set air conditioner mode",
              "return_type": "VOID",
              "descriptor": "Controls air conditioner mode and temperature settings"
            },
            {
              "service": "SetTargetTemperature",
              "canonical_name": "AirConditioner_SetTargetTemperature",
              "canonical_name_lower": "airconditioner_settargettemperature",
              "type": "function",
              "argument_type": "DOUBLE",
              "argument_bounds": "Temperature to set",
              "argument_descriptor": "Set air conditioner temperature",
              "return_type": "VOID",
              "descriptor": "Controls air conditioner mode and temperature settings"
            },
            {
              "service": "TargetTemperature",
              "canonical_name": "AirConditioner_TargetTemperature",
              "canonical_name_lower": "airconditioner_targettemperature",
              "type": "value",
              "return_type": "DOUBLE",
              "return_descriptor": "Current set air conditioner temperature",
              "descriptor": "Controls air conditioner mode and temperature settings"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::AirPurifier",
      "source": "service_schema_fallback",
      "categories": [
        "AirPurifier"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "AirPurifier",
          "category_tag": "#AirPurifier",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#AirPurifier)",
            "all(#AirPurifier)"
          ],
          "services": [
            {
              "service": "AirPurifierMode",
              "canonical_name": "AirPurifier_AirPurifierMode",
              "canonical_name_lower": "airpurifier_airpurifiermode",
              "type": "value",
              "return_type": "ENUM",
              "return_descriptor": "Current air purifier mode",
              "descriptor": "Controls air purifier mode",
              "enums": [
                "auto",
                "sleep",
                "low",
                "medium",
                "high",
                "quiet",
                "windFree",
                "off"
              ]
            },
            {
              "service": "SetAirPurifierMode",
              "canonical_name": "AirPurifier_SetAirPurifierMode",
              "canonical_name_lower": "airpurifier_setairpurifiermode",
              "type": "function",
              "argument_type": "ENUM",
              "argument_bounds": "Air purifier mode to set",
              "argument_descriptor": "Set air purifier mode",
              "return_type": "VOID",
              "descriptor": "Controls air purifier mode"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::AirQualitySensor",
      "source": "service_schema_fallback",
      "categories": [
        "AirQualitySensor"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "AirQualitySensor",
          "category_tag": "#AirQualitySensor",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#AirQualitySensor)",
            "all(#AirQualitySensor)"
          ],
          "services": [
            {
              "service": "CarbonDioxide",
              "canonical_name": "AirQualitySensor_CarbonDioxide",
              "canonical_name_lower": "airqualitysensor_carbondioxide",
              "type": "value",
              "return_type": "DOUBLE",
              "return_bounds": [
                0,
                50000
              ],
              "return_descriptor": "CO2 concentration in ppm",
              "descriptor": "Air quality detector device for comprehensive air quality monitoring"
            },
            {
              "service": "DustLevel",
              "canonical_name": "AirQualitySensor_DustLevel",
              "canonical_name_lower": "airqualitysensor_dustlevel",
              "type": "value",
              "return_type": "DOUBLE",
              "return_bounds": [
                0,
                1000
              ],
              "return_descriptor": "Dust (PM10) level",
              "descriptor": "Air quality detector device for comprehensive air quality monitoring"
            },
            {
              "service": "FineDustLevel",
              "canonical_name": "AirQualitySensor_FineDustLevel",
              "canonical_name_lower": "airqualitysensor_finedustlevel",
              "type": "value",
              "return_type": "DOUBLE",
              "return_bounds": [
                0,
                1000
              ],
              "return_descriptor": "Fine dust (PM2.5) level",
              "descriptor": "Air quality detector device for comprehensive air quality monitoring"
            },
            {
              "service": "Humidity",
              "canonical_name": "AirQualitySensor_Humidity",
              "canonical_name_lower": "airqualitysensor_humidity",
              "type": "value",
              "return_type": "DOUBLE",
              "return_bounds": [
                0,
                100
              ],
              "return_descriptor": "Humidity in %",
              "descriptor": "Air quality detector device for comprehensive air quality monitoring"
            },
            {
              "service": "Temperature",
              "canonical_name": "AirQualitySensor_Temperature",
              "canonical_name_lower": "airqualitysensor_temperature",
              "type": "value",
              "return_type": "DOUBLE",
              "return_bounds": [
                -40,
                60
              ],
              "return_descriptor": "Temperature in °C",
              "descriptor": "Air quality detector device for comprehensive air quality monitoring"
            },
            {
              "service": "TvocLevel",
              "canonical_name": "AirQualitySensor_TvocLevel",
              "canonical_name_lower": "airqualitysensor_tvoclevel",
              "type": "value",
              "return_type": "DOUBLE",
              "return_bounds": [
                0,
                60000
              ],
              "return_descriptor": "TVOC level in ppb",
              "descriptor": "Air quality detector device for comprehensive air quality monitoring"
            },
            {
              "service": "VeryFineDustLevel",
              "canonical_name": "AirQualitySensor_VeryFineDustLevel",
              "canonical_name_lower": "airqualitysensor_veryfinedustlevel",
              "type": "value",
              "return_type": "DOUBLE",
              "return_bounds": [
                0,
                1000
              ],
              "return_descriptor": "Very fine dust (PM1.0) level",
              "descriptor": "Air quality detector device for comprehensive air quality monitoring"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::ArmRobot",
      "source": "service_schema_fallback",
      "categories": [
        "ArmRobot"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "ArmRobot",
          "category_tag": "#ArmRobot",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#ArmRobot)",
            "all(#ArmRobot)"
          ],
          "services": [
            {
              "service": "ArmRobotType",
              "canonical_name": "ArmRobot_ArmRobotType",
              "canonical_name_lower": "armrobot_armrobottype",
              "type": "value",
              "return_type": "ENUM",
              "return_descriptor": "Current status of the arm robot type",
              "descriptor": "Allows for the control of the arm robot",
              "enums": [
                "mycobot280_pi"
              ]
            },
            {
              "service": "CurrentPosition",
              "canonical_name": "ArmRobot_CurrentPosition",
              "canonical_name_lower": "armrobot_currentposition",
              "type": "value",
              "return_type": "STRING",
              "return_descriptor": "Current status of the arm robot position",
              "descriptor": "Allows for the control of the arm robot"
            },
            {
              "service": "Hello",
              "canonical_name": "ArmRobot_Hello",
              "canonical_name_lower": "armrobot_hello",
              "type": "function",
              "argument_descriptor": "Send hello command to arm robot",
              "return_type": "VOID",
              "descriptor": "Allows for the control of the arm robot"
            },
            {
              "service": "SendCommand",
              "canonical_name": "ArmRobot_SendCommand",
              "canonical_name_lower": "armrobot_sendcommand",
              "type": "function",
              "argument_type": "ENUM",
              "argument_bounds": "Command to send to the arm robot. List of string, separated by ','",
              "argument_descriptor": "Send command to arm robot",
              "return_type": "VOID",
              "descriptor": "Allows for the control of the arm robot"
            },
            {
              "service": "SetPosition",
              "canonical_name": "ArmRobot_SetPosition",
              "canonical_name_lower": "armrobot_setposition",
              "type": "function",
              "argument_type": "ENUM",
              "argument_bounds": "Position to set for the arm robot (home, hello, refuse)",
              "argument_descriptor": "Send position to arm robot",
              "return_type": "VOID",
              "descriptor": "Allows for the control of the arm robot"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::AudioRecorder",
      "source": "service_schema_fallback",
      "categories": [
        "AudioRecorder"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "AudioRecorder",
          "category_tag": "#AudioRecorder",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#AudioRecorder)",
            "all(#AudioRecorder)"
          ],
          "services": [
            {
              "service": "AudioFile",
              "canonical_name": "AudioRecorder_AudioFile",
              "canonical_name_lower": "audiorecorder_audiofile",
              "type": "value",
              "return_type": "BINARY",
              "return_descriptor": "The current audio file of the audio recorder",
              "descriptor": "Record audio"
            },
            {
              "service": "RecordStart",
              "canonical_name": "AudioRecorder_RecordStart",
              "canonical_name_lower": "audiorecorder_recordstart",
              "type": "function",
              "argument_descriptor": "Start recording audio",
              "return_type": "VOID",
              "descriptor": "Record audio"
            },
            {
              "service": "RecordStatus",
              "canonical_name": "AudioRecorder_RecordStatus",
              "canonical_name_lower": "audiorecorder_recordstatus",
              "type": "value",
              "return_type": "ENUM",
              "return_descriptor": "The current status of the audio recorder",
              "descriptor": "Record audio",
              "enums": [
                "idle",
                "recording"
              ]
            },
            {
              "service": "RecordStop",
              "canonical_name": "AudioRecorder_RecordStop",
              "canonical_name_lower": "audiorecorder_recordstop",
              "type": "function",
              "argument_type": "BINARY",
              "argument_bounds": "The file to save the recording to",
              "argument_descriptor": "Stop recording audio",
              "return_type": "VOID",
              "descriptor": "Record audio"
            },
            {
              "service": "RecordWithDuration",
              "canonical_name": "AudioRecorder_RecordWithDuration",
              "canonical_name_lower": "audiorecorder_recordwithduration",
              "type": "function",
              "argument_type": "STRING | DOUBLE",
              "argument_bounds": "The file to record to, The duration to record for",
              "argument_format": ",",
              "argument_descriptor": "Record audio with a specified duration",
              "return_type": "BINARY",
              "descriptor": "Record audio"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::Button",
      "source": "service_schema_fallback",
      "categories": [
        "Button"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "Button",
          "category_tag": "#Button",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#Button)",
            "all(#Button)"
          ],
          "services": [
            {
              "service": "Button",
              "canonical_name": "Button_Button",
              "canonical_name_lower": "button_button",
              "type": "value",
              "return_type": "ENUM",
              "return_descriptor": "Button state",
              "descriptor": "A device with one or more buttons",
              "enums": [
                "pushed",
                "held",
                "double",
                "pushed_2x",
                "pushed_3x",
                "pushed_4x",
                "pushed_5x",
                "pushed_6x",
                "down",
                "down_2x",
                "down_3x",
                "down_4x",
                "down_5x",
                "down_6x",
                "down_hold",
                "up",
                "up_2x",
                "up_3x",
                "up_4x",
                "up_5x",
                "up_6x",
                "up_hold",
                "swipe_up",
                "swipe_down",
                "swipe_left",
                "swipe_right"
              ]
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::Camera",
      "source": "service_schema_fallback",
      "categories": [
        "Camera"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "Camera",
          "category_tag": "#Camera",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#Camera)",
            "all(#Camera)"
          ],
          "services": [
            {
              "service": "CameraState",
              "canonical_name": "Camera_CameraState",
              "canonical_name_lower": "camera_camerastate",
              "type": "value",
              "return_type": "ENUM",
              "return_descriptor": "Current camera state",
              "descriptor": "Controls camera device for image/video capture and streaming",
              "enums": [
                "off",
                "on",
                "restarting",
                "unavailable"
              ]
            },
            {
              "service": "CaptureImage",
              "canonical_name": "Camera_CaptureImage",
              "canonical_name_lower": "camera_captureimage",
              "type": "function",
              "argument_descriptor": "Take a picture with the camera - Return the image as binary data",
              "return_type": "BINARY",
              "descriptor": "Controls camera device for image/video capture and streaming"
            },
            {
              "service": "CaptureVideo",
              "canonical_name": "Camera_CaptureVideo",
              "canonical_name_lower": "camera_capturevideo",
              "type": "function",
              "argument_descriptor": "Take a video with the camera - Return the video as binary data",
              "return_type": "BINARY",
              "descriptor": "Controls camera device for image/video capture and streaming"
            },
            {
              "service": "Image",
              "canonical_name": "Camera_Image",
              "canonical_name_lower": "camera_image",
              "type": "value",
              "return_type": "BINARY",
              "return_descriptor": "The latest image captured by the camera",
              "descriptor": "Controls camera device for image/video capture and streaming"
            },
            {
              "service": "StartStream",
              "canonical_name": "Camera_StartStream",
              "canonical_name_lower": "camera_startstream",
              "type": "function",
              "argument_descriptor": "Start the camera stream - Return the stream URL",
              "return_type": "STRING",
              "descriptor": "Controls camera device for image/video capture and streaming"
            },
            {
              "service": "StopStream",
              "canonical_name": "Camera_StopStream",
              "canonical_name_lower": "camera_stopstream",
              "type": "function",
              "argument_descriptor": "Stop the camera stream",
              "return_type": "VOID",
              "descriptor": "Controls camera device for image/video capture and streaming"
            },
            {
              "service": "Stream",
              "canonical_name": "Camera_Stream",
              "canonical_name_lower": "camera_stream",
              "type": "value",
              "return_type": "STRING",
              "return_descriptor": "The current video stream from the camera",
              "descriptor": "Controls camera device for image/video capture and streaming"
            },
            {
              "service": "Video",
              "canonical_name": "Camera_Video",
              "canonical_name_lower": "camera_video",
              "type": "value",
              "return_type": "BINARY",
              "return_descriptor": "The latest video captured by the camera",
              "descriptor": "Controls camera device for image/video capture and streaming"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::CarbonDioxideSensor",
      "source": "service_schema_fallback",
      "categories": [
        "CarbonDioxideSensor"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "CarbonDioxideSensor",
          "category_tag": "#CarbonDioxideSensor",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#CarbonDioxideSensor)",
            "all(#CarbonDioxideSensor)"
          ],
          "services": [
            {
              "service": "CarbonDioxide",
              "canonical_name": "CarbonDioxideSensor_CarbonDioxide",
              "canonical_name_lower": "carbondioxidesensor_carbondioxide",
              "type": "value",
              "return_type": "DOUBLE",
              "return_bounds": [
                0,
                1000000
              ],
              "return_descriptor": "The level of carbon dioxide detected",
              "descriptor": "Measure carbon dioxide levels"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::Charger",
      "source": "service_schema_fallback",
      "categories": [
        "Charger"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "Charger",
          "category_tag": "#Charger",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#Charger)",
            "all(#Charger)"
          ],
          "services": [
            {
              "service": "ChargingState",
              "canonical_name": "Charger_ChargingState",
              "canonical_name_lower": "charger_chargingstate",
              "type": "value",
              "return_type": "ENUM",
              "return_descriptor": "The current charging state of the device",
              "descriptor": "The current status of battery charging",
              "enums": [
                "charging",
                "discharging",
                "stopped",
                "fullyCharged",
                "error"
              ]
            },
            {
              "service": "Current",
              "canonical_name": "Charger_Current",
              "canonical_name_lower": "charger_current",
              "type": "value",
              "return_type": "DOUBLE",
              "return_descriptor": "The current flowing into or out of the battery in amperes",
              "descriptor": "The current status of battery charging"
            },
            {
              "service": "Power",
              "canonical_name": "Charger_Power",
              "canonical_name_lower": "charger_power",
              "type": "value",
              "return_type": "DOUBLE",
              "return_descriptor": "The power consumption of the device in watts",
              "descriptor": "The current status of battery charging"
            },
            {
              "service": "Voltage",
              "canonical_name": "Charger_Voltage",
              "canonical_name_lower": "charger_voltage",
              "type": "value",
              "return_type": "DOUBLE",
              "return_descriptor": "The voltage of the battery in millivolts",
              "descriptor": "The current status of battery charging"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::Clock",
      "source": "service_schema_fallback",
      "categories": [
        "Clock"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "Clock",
          "category_tag": "#Clock",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#Clock)",
            "all(#Clock)"
          ],
          "services": [
            {
              "service": "Date",
              "canonical_name": "Clock_Date",
              "canonical_name_lower": "clock_date",
              "type": "value",
              "return_type": "STRING",
              "return_descriptor": "Current date as string - format: YYYYMMdd",
              "descriptor": "Provide current date and time"
            },
            {
              "service": "Datetime",
              "canonical_name": "Clock_Datetime",
              "canonical_name_lower": "clock_datetime",
              "type": "value",
              "return_type": "STRING",
              "return_descriptor": "Current date and time as string - format: YYYYMMddhhmm",
              "descriptor": "Provide current date and time"
            },
            {
              "service": "Day",
              "canonical_name": "Clock_Day",
              "canonical_name_lower": "clock_day",
              "type": "value",
              "return_type": "INTEGER",
              "return_bounds": [
                1,
                31
              ],
              "return_descriptor": "Current day",
              "descriptor": "Provide current date and time"
            },
            {
              "service": "Delay",
              "canonical_name": "Clock_Delay",
              "canonical_name_lower": "clock_delay",
              "type": "function",
              "argument_type": "INTEGER | INTEGER | INTEGER",
              "argument_bounds": "hour, minute, second",
              "argument_format": ",",
              "argument_descriptor": "delay for a given amount of time",
              "return_type": "VOID",
              "descriptor": "Provide current date and time"
            },
            {
              "service": "Hour",
              "canonical_name": "Clock_Hour",
              "canonical_name_lower": "clock_hour",
              "type": "value",
              "return_type": "INTEGER",
              "return_bounds": [
                0,
                24
              ],
              "return_descriptor": "Current hour",
              "descriptor": "Provide current date and time"
            },
            {
              "service": "IsHoliday",
              "canonical_name": "Clock_IsHoliday",
              "canonical_name_lower": "clock_isholiday",
              "type": "value",
              "return_type": "BOOL",
              "return_descriptor": "Whether today is a holiday",
              "descriptor": "Provide current date and time"
            },
            {
              "service": "Minute",
              "canonical_name": "Clock_Minute",
              "canonical_name_lower": "clock_minute",
              "type": "value",
              "return_type": "INTEGER",
              "return_bounds": [
                0,
                60
              ],
              "return_descriptor": "Current minute",
              "descriptor": "Provide current date and time"
            },
            {
              "service": "Month",
              "canonical_name": "Clock_Month",
              "canonical_name_lower": "clock_month",
              "type": "value",
              "return_type": "INTEGER",
              "return_bounds": [
                1,
                12
              ],
              "return_descriptor": "Current month",
              "descriptor": "Provide current date and time"
            },
            {
              "service": "Second",
              "canonical_name": "Clock_Second",
              "canonical_name_lower": "clock_second",
              "type": "value",
              "return_type": "INTEGER",
              "return_bounds": [
                0,
                60
              ],
              "return_descriptor": "Current second",
              "descriptor": "Provide current date and time"
            },
            {
              "service": "Time",
              "canonical_name": "Clock_Time",
              "canonical_name_lower": "clock_time",
              "type": "value",
              "return_type": "STRING",
              "return_descriptor": "Current time as string - format: hhmm",
              "descriptor": "Provide current date and time"
            },
            {
              "service": "Timestamp",
              "canonical_name": "Clock_Timestamp",
              "canonical_name_lower": "clock_timestamp",
              "type": "value",
              "return_type": "DOUBLE",
              "return_descriptor": "Current timestamp (return current unix time - unit: seconds with floating point)",
              "descriptor": "Provide current date and time"
            },
            {
              "service": "Weekday",
              "canonical_name": "Clock_Weekday",
              "canonical_name_lower": "clock_weekday",
              "type": "value",
              "return_type": "ENUM",
              "return_descriptor": "Current weekday",
              "descriptor": "Provide current date and time",
              "enums": [
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "sunday"
              ]
            },
            {
              "service": "Year",
              "canonical_name": "Clock_Year",
              "canonical_name_lower": "clock_year",
              "type": "value",
              "return_type": "INTEGER",
              "return_bounds": [
                0,
                100000
              ],
              "return_descriptor": "Current year",
              "descriptor": "Provide current date and time"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::CloudServiceProvider",
      "source": "service_schema_fallback",
      "categories": [
        "CloudServiceProvider"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "CloudServiceProvider",
          "category_tag": "#CloudServiceProvider",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#CloudServiceProvider)",
            "all(#CloudServiceProvider)"
          ],
          "services": [
            {
              "service": "ChatSession",
              "canonical_name": "CloudServiceProvider_ChatSession",
              "canonical_name_lower": "cloudserviceprovider_chatsession",
              "type": "value",
              "return_type": "STRING",
              "return_descriptor": "Represents a chat session with an AI model via the cloud service",
              "descriptor": "Provides cloud service functionalities"
            },
            {
              "service": "ChatWithAI",
              "canonical_name": "CloudServiceProvider_ChatWithAI",
              "canonical_name_lower": "cloudserviceprovider_chatwithai",
              "type": "function",
              "argument_type": "STRING",
              "argument_bounds": "The text prompt to chat with the AI model",
              "argument_descriptor": "Chat with an AI model using the cloud service",
              "return_type": "STRING",
              "descriptor": "Provides cloud service functionalities"
            },
            {
              "service": "ExplainImage",
              "canonical_name": "CloudServiceProvider_ExplainImage",
              "canonical_name_lower": "cloudserviceprovider_explainimage",
              "type": "function",
              "argument_type": "BINARY",
              "argument_bounds": "Image file to be explained",
              "argument_descriptor": "Explain an image and return a description using the cloud service",
              "return_type": "STRING",
              "descriptor": "Provides cloud service functionalities"
            },
            {
              "service": "GenerateImage",
              "canonical_name": "CloudServiceProvider_GenerateImage",
              "canonical_name_lower": "cloudserviceprovider_generateimage",
              "type": "function",
              "argument_type": "STRING",
              "argument_bounds": "The text prompt to generate the image from",
              "argument_descriptor": "Generate an image based on a text prompt using the cloud service",
              "return_type": "BINARY",
              "descriptor": "Provides cloud service functionalities"
            },
            {
              "service": "GeneratedImage",
              "canonical_name": "CloudServiceProvider_GeneratedImage",
              "canonical_name_lower": "cloudserviceprovider_generatedimage",
              "type": "value",
              "return_type": "BINARY",
              "return_descriptor": "Represents an image generated by the cloud service",
              "descriptor": "Provides cloud service functionalities"
            },
            {
              "service": "ImageExplanation",
              "canonical_name": "CloudServiceProvider_ImageExplanation",
              "canonical_name_lower": "cloudserviceprovider_imageexplanation",
              "type": "value",
              "return_type": "STRING",
              "return_descriptor": "Represents the description of an image explained by the cloud service",
              "descriptor": "Provides cloud service functionalities"
            },
            {
              "service": "IsAvailable",
              "canonical_name": "CloudServiceProvider_IsAvailable",
              "canonical_name_lower": "cloudserviceprovider_isavailable",
              "type": "function",
              "argument_type": "BOOL",
              "argument_bounds": "The name of the cloud service to check",
              "argument_descriptor": "Check if the cloud service is available",
              "return_type": "BOOL",
              "descriptor": "Provides cloud service functionalities"
            },
            {
              "service": "LLMModels",
              "canonical_name": "CloudServiceProvider_LLMModels",
              "canonical_name_lower": "cloudserviceprovider_llmmodels",
              "type": "value",
              "return_type": "LIST",
              "return_descriptor": "Represents the available large language models provided by the cloud service",
              "descriptor": "Provides cloud service functionalities"
            },
            {
              "service": "SaveToFile",
              "canonical_name": "CloudServiceProvider_SaveToFile",
              "canonical_name_lower": "cloudserviceprovider_savetofile",
              "type": "function",
              "argument_type": "BINARY | STRING",
              "argument_bounds": "The base64 data to save to the file, Path of the file to save data to",
              "argument_format": ",",
              "argument_descriptor": "Save data to a file in local",
              "return_type": "STRING",
              "descriptor": "Provides cloud service functionalities"
            },
            {
              "service": "SpeechToText",
              "canonical_name": "CloudServiceProvider_SpeechToText",
              "canonical_name_lower": "cloudserviceprovider_speechtotext",
              "type": "function",
              "argument_type": "STRING",
              "argument_bounds": "Audio file containing the speech to convert",
              "argument_descriptor": "Convert speech to text using the cloud service",
              "return_type": "STRING",
              "descriptor": "Provides cloud service functionalities"
            },
            {
              "service": "TextToSpeech",
              "canonical_name": "CloudServiceProvider_TextToSpeech",
              "canonical_name_lower": "cloudserviceprovider_texttospeech",
              "type": "function",
              "argument_type": "STRING",
              "argument_bounds": "Text to be converted to speech",
              "argument_descriptor": "Convert text to speech using the cloud service",
              "return_type": "BINARY",
              "descriptor": "Provides cloud service functionalities"
            },
            {
              "service": "UploadFile",
              "canonical_name": "CloudServiceProvider_UploadFile",
              "canonical_name_lower": "cloudserviceprovider_uploadfile",
              "type": "function",
              "argument_type": "STRING",
              "argument_bounds": "File to upload to the cloud service",
              "argument_descriptor": "Upload file to the cloud service",
              "return_type": "BINARY",
              "descriptor": "Provides cloud service functionalities"
            },
            {
              "service": "UploadToCloudStorage",
              "canonical_name": "CloudServiceProvider_UploadToCloudStorage",
              "canonical_name_lower": "cloudserviceprovider_uploadtocloudstorage",
              "type": "function",
              "argument_type": "STRING",
              "argument_bounds": "Path of the file or Base64 data to upload to cloud storage",
              "argument_descriptor": "Upload a file to cloud storage",
              "return_type": "STRING",
              "descriptor": "Provides cloud service functionalities"
            },
            {
              "service": "UploadedFile",
              "canonical_name": "CloudServiceProvider_UploadedFile",
              "canonical_name_lower": "cloudserviceprovider_uploadedfile",
              "type": "value",
              "return_type": "BINARY",
              "return_descriptor": "Represents a file that has been uploaded to the cloud service",
              "descriptor": "Provides cloud service functionalities"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::ColorControl",
      "source": "service_schema_fallback",
      "categories": [
        "ColorControl"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "ColorControl",
          "category_tag": "#ColorControl",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#ColorControl)",
            "all(#ColorControl)"
          ],
          "services": [
            {
              "service": "Color",
              "canonical_name": "ColorControl_Color",
              "canonical_name_lower": "colorcontrol_color",
              "type": "value",
              "return_type": "STRING",
              "return_descriptor": "Current color in RGB format (r|g|b)",
              "descriptor": "Allows for control of a color changing device"
            },
            {
              "service": "SetColor",
              "canonical_name": "ColorControl_SetColor",
              "canonical_name_lower": "colorcontrol_setcolor",
              "type": "function",
              "argument_type": "STRING",
              "argument_bounds": "RGB color value in format 'r,g,b' (0-255 for each)",
              "argument_descriptor": "Set the color of the device",
              "return_type": "VOID",
              "descriptor": "Allows for control of a color changing device"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::ContactSensor",
      "source": "service_schema_fallback",
      "categories": [
        "ContactSensor"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "ContactSensor",
          "category_tag": "#ContactSensor",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#ContactSensor)",
            "all(#ContactSensor)"
          ],
          "services": [
            {
              "service": "Contact",
              "canonical_name": "ContactSensor_Contact",
              "canonical_name_lower": "contactsensor_contact",
              "type": "value",
              "return_type": "BOOL",
              "return_descriptor": "The current state of the contact sensor. True if the sensor is closed, False if it is open.",
              "descriptor": "Allows reading the value of a contact sensor device"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::Dehumidifier",
      "source": "service_schema_fallback",
      "categories": [
        "Dehumidifier"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "Dehumidifier",
          "category_tag": "#Dehumidifier",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#Dehumidifier)",
            "all(#Dehumidifier)"
          ],
          "services": [
            {
              "service": "DehumidifierMode",
              "canonical_name": "Dehumidifier_DehumidifierMode",
              "canonical_name_lower": "dehumidifier_dehumidifiermode",
              "type": "value",
              "return_type": "ENUM",
              "return_descriptor": "Current mode of the dehumidifier",
              "descriptor": "Allows for the control of the dehumidifier mode",
              "enums": [
                "cooling",
                "delayWash",
                "drying",
                "finished",
                "refreshing",
                "weightSensing",
                "wrinklePrevent",
                "dehumidifying",
                "AIDrying",
                "sanitizing",
                "internalCare",
                "freezeProtection",
                "continuousDehumidifying",
                "thawingFrozenInside"
              ]
            },
            {
              "service": "SetDehumidifierMode",
              "canonical_name": "Dehumidifier_SetDehumidifierMode",
              "canonical_name_lower": "dehumidifier_setdehumidifiermode",
              "type": "function",
              "argument_type": "ENUM",
              "argument_bounds": "Set the dehumidifier mode",
              "argument_descriptor": "Set the dehumidifier mode",
              "return_type": "VOID",
              "descriptor": "Allows for the control of the dehumidifier mode"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::DimmerSwitch",
      "source": "service_schema_fallback",
      "categories": [
        "DimmerSwitch"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "DimmerSwitch",
          "category_tag": "#DimmerSwitch",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#DimmerSwitch)",
            "all(#DimmerSwitch)"
          ],
          "services": [
            {
              "service": "Button1",
              "canonical_name": "DimmerSwitch_Button1",
              "canonical_name_lower": "dimmerswitch_button1",
              "type": "value",
              "return_type": "ENUM",
              "return_descriptor": "Button 1 state",
              "descriptor": "A dimmer switch device with multiple buttons (typically 4 buttons)",
              "enums": [
                "pushed",
                "held",
                "double",
                "pushed_2x",
                "pushed_3x",
                "down",
                "down_hold",
                "up",
                "up_hold"
              ]
            },
            {
              "service": "Button2",
              "canonical_name": "DimmerSwitch_Button2",
              "canonical_name_lower": "dimmerswitch_button2",
              "type": "value",
              "return_type": "ENUM",
              "return_descriptor": "Button 2 state",
              "descriptor": "A dimmer switch device with multiple buttons (typically 4 buttons)"
            },
            {
              "service": "Button3",
              "canonical_name": "DimmerSwitch_Button3",
              "canonical_name_lower": "dimmerswitch_button3",
              "type": "value",
              "return_type": "ENUM",
              "return_descriptor": "Button 3 state",
              "descriptor": "A dimmer switch device with multiple buttons (typically 4 buttons)"
            },
            {
              "service": "Button4",
              "canonical_name": "DimmerSwitch_Button4",
              "canonical_name_lower": "dimmerswitch_button4",
              "type": "value",
              "return_type": "ENUM",
              "return_descriptor": "Button 4 state",
              "descriptor": "A dimmer switch device with multiple buttons (typically 4 buttons)"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::Dishwasher",
      "source": "service_schema_fallback",
      "categories": [
        "Dishwasher"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "Dishwasher",
          "category_tag": "#Dishwasher",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#Dishwasher)",
            "all(#Dishwasher)"
          ],
          "services": [
            {
              "service": "DishwasherMode",
              "canonical_name": "Dishwasher_DishwasherMode",
              "canonical_name_lower": "dishwasher_dishwashermode",
              "type": "value",
              "return_type": "ENUM",
              "return_descriptor": "Current mode of the dishwasher",
              "descriptor": "Allows for the control of the dishwasher mode",
              "enums": [
                "eco",
                "intense",
                "auto",
                "quick",
                "rinse",
                "dry"
              ]
            },
            {
              "service": "SetDishwasherMode",
              "canonical_name": "Dishwasher_SetDishwasherMode",
              "canonical_name_lower": "dishwasher_setdishwashermode",
              "type": "function",
              "argument_type": "ENUM",
              "argument_bounds": "Set the dishwasher mode to \"eco\", \"intense\", \"auto\", \"quick\", \"rinse\", or \"dry\" mode",
              "argument_descriptor": "Set the dishwasher mode",
              "return_type": "VOID",
              "descriptor": "Allows for the control of the dishwasher mode"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::Door",
      "source": "service_schema_fallback",
      "categories": [
        "Door"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "Door",
          "category_tag": "#Door",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#Door)",
            "all(#Door)"
          ],
          "services": [
            {
              "service": "Close",
              "canonical_name": "Door_Close",
              "canonical_name_lower": "door_close",
              "type": "function",
              "argument_descriptor": "Close the door",
              "return_type": "VOID",
              "descriptor": "Allow for the control of a door"
            },
            {
              "service": "DoorState",
              "canonical_name": "Door_DoorState",
              "canonical_name_lower": "door_doorstate",
              "type": "value",
              "return_type": "ENUM",
              "return_descriptor": "The current state of the door",
              "descriptor": "Allow for the control of a door",
              "enums": [
                "closed",
                "closing",
                "open",
                "opening",
                "unknown"
              ]
            },
            {
              "service": "Open",
              "canonical_name": "Door_Open",
              "canonical_name_lower": "door_open",
              "type": "function",
              "argument_descriptor": "Open the door",
              "return_type": "VOID",
              "descriptor": "Allow for the control of a door"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::DoorLock",
      "source": "service_schema_fallback",
      "categories": [
        "DoorLock"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "DoorLock",
          "category_tag": "#DoorLock",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#DoorLock)",
            "all(#DoorLock)"
          ],
          "services": [
            {
              "service": "DoorLockState",
              "canonical_name": "DoorLock_DoorLockState",
              "canonical_name_lower": "doorlock_doorlockstate",
              "type": "value",
              "return_type": "ENUM",
              "return_descriptor": "The current state of the door lock",
              "descriptor": "Allow for the control of a door lock",
              "enums": [
                "closed",
                "closing",
                "open",
                "opening",
                "unknown"
              ]
            },
            {
              "service": "Lock",
              "canonical_name": "DoorLock_Lock",
              "canonical_name_lower": "doorlock_lock",
              "type": "function",
              "argument_descriptor": "Lock the door",
              "return_type": "VOID",
              "descriptor": "Allow for the control of a door lock"
            },
            {
              "service": "Unlock",
              "canonical_name": "DoorLock_Unlock",
              "canonical_name_lower": "doorlock_unlock",
              "type": "function",
              "argument_descriptor": "Unlock the door",
              "return_type": "VOID",
              "descriptor": "Allow for the control of a door lock"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::EmailProvider",
      "source": "service_schema_fallback",
      "categories": [
        "EmailProvider"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "EmailProvider",
          "category_tag": "#EmailProvider",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#EmailProvider)",
            "all(#EmailProvider)"
          ],
          "services": [
            {
              "service": "SendMail",
              "canonical_name": "EmailProvider_SendMail",
              "canonical_name_lower": "emailprovider_sendmail",
              "type": "function",
              "argument_type": "STRING | STRING | STRING",
              "argument_bounds": "The email address of the recipient, The title of the email, The body content of the email",
              "argument_format": ",",
              "argument_descriptor": "Send an email to the specified recipient",
              "return_type": "VOID",
              "descriptor": "Provides email service"
            },
            {
              "service": "SendMailWithFile",
              "canonical_name": "EmailProvider_SendMailWithFile",
              "canonical_name_lower": "emailprovider_sendmailwithfile",
              "type": "function",
              "argument_type": "STRING | STRING | STRING | STRING",
              "argument_bounds": "The email address of the recipient, The title of the email, The body content of the email, The file path of the attachment or base64 encoded string",
              "argument_format": ",",
              "argument_descriptor": "Send an email with an attachment to the specified recipient",
              "return_type": "VOID",
              "descriptor": "Provides email service"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::FaceRecognizer",
      "source": "service_schema_fallback",
      "categories": [
        "FaceRecognizer"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "FaceRecognizer",
          "category_tag": "#FaceRecognizer",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#FaceRecognizer)",
            "all(#FaceRecognizer)"
          ],
          "services": [
            {
              "service": "AddFace",
              "canonical_name": "FaceRecognizer_AddFace",
              "canonical_name_lower": "facerecognizer_addface",
              "type": "function",
              "argument_type": "STRING",
              "argument_bounds": "ID for the new face",
              "argument_descriptor": "Add a new face to the recognition database",
              "return_type": "BOOL",
              "descriptor": "Controls face recognition features"
            },
            {
              "service": "DeleteFace",
              "canonical_name": "FaceRecognizer_DeleteFace",
              "canonical_name_lower": "facerecognizer_deleteface",
              "type": "function",
              "argument_type": "STRING",
              "argument_bounds": "ID of the face to delete",
              "argument_descriptor": "Delete a face from the recognition database",
              "return_type": "BOOL",
              "descriptor": "Controls face recognition features"
            },
            {
              "service": "End",
              "canonical_name": "FaceRecognizer_End",
              "canonical_name_lower": "facerecognizer_end",
              "type": "function",
              "argument_descriptor": "End face recognition",
              "return_type": "BOOL",
              "descriptor": "Controls face recognition features"
            },
            {
              "service": "RecognizedResult",
              "canonical_name": "FaceRecognizer_RecognizedResult",
              "canonical_name_lower": "facerecognizer_recognizedresult",
              "type": "value",
              "return_type": "STRING",
              "return_descriptor": "ID of the currently recognized face",
              "descriptor": "Controls face recognition features"
            },
            {
              "service": "Start",
              "canonical_name": "FaceRecognizer_Start",
              "canonical_name_lower": "facerecognizer_start",
              "type": "function",
              "argument_descriptor": "Start face recognition",
              "return_type": "BOOL",
              "descriptor": "Controls face recognition features"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::Humidifier",
      "source": "service_schema_fallback",
      "categories": [
        "Humidifier"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "Humidifier",
          "category_tag": "#Humidifier",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#Humidifier)",
            "all(#Humidifier)"
          ],
          "services": [
            {
              "service": "HumidifierMode",
              "canonical_name": "Humidifier_HumidifierMode",
              "canonical_name_lower": "humidifier_humidifiermode",
              "type": "value",
              "return_type": "ENUM",
              "return_descriptor": "Current mode of the humidifier",
              "descriptor": "Maintains and sets the state of an humidifier",
              "enums": [
                "auto -",
                "low -",
                "medium -",
                "high -"
              ]
            },
            {
              "service": "SetHumidifierMode",
              "canonical_name": "Humidifier_SetHumidifierMode",
              "canonical_name_lower": "humidifier_sethumidifiermode",
              "type": "function",
              "argument_type": "ENUM",
              "argument_bounds": "Set the humidifier mode to \"auto\", \"low\", \"medium\", or \"high\" mode",
              "argument_descriptor": "Set the humidifier mode",
              "return_type": "VOID",
              "descriptor": "Maintains and sets the state of an humidifier"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::HumiditySensor",
      "source": "service_schema_fallback",
      "categories": [
        "HumiditySensor"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "HumiditySensor",
          "category_tag": "#HumiditySensor",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#HumiditySensor)",
            "all(#HumiditySensor)"
          ],
          "services": [
            {
              "service": "Humidity",
              "canonical_name": "HumiditySensor_Humidity",
              "canonical_name_lower": "humiditysensor_humidity",
              "type": "value",
              "return_type": "DOUBLE",
              "return_bounds": [
                0,
                100
              ],
              "return_descriptor": "A numerical representation of the relative humidity measurement taken by the device",
              "descriptor": "Allow reading the relative humidity from devices that support it"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::LaundryDryer",
      "source": "service_schema_fallback",
      "categories": [
        "LaundryDryer"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "LaundryDryer",
          "category_tag": "#LaundryDryer",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#LaundryDryer)",
            "all(#LaundryDryer)"
          ],
          "services": [
            {
              "service": "LaundryDryerMode",
              "canonical_name": "LaundryDryer_LaundryDryerMode",
              "canonical_name_lower": "laundrydryer_laundrydryermode",
              "type": "value",
              "return_type": "ENUM",
              "return_descriptor": "Current mode of the laundry dryer",
              "descriptor": "Allows for the control of the laundry dryer mode",
              "enums": [
                "auto",
                "quick",
                "quiet",
                "lownoise",
                "lowenergy",
                "vacation",
                "min",
                "max",
                "night",
                "day",
                "normal",
                "delicate",
                "heavy",
                "whites"
              ]
            },
            {
              "service": "SetLaundryDryerMode",
              "canonical_name": "LaundryDryer_SetLaundryDryerMode",
              "canonical_name_lower": "laundrydryer_setlaundrydryermode",
              "type": "function",
              "argument_type": "ENUM",
              "argument_bounds": "Set the laundry dryer mode",
              "argument_descriptor": "Set the laundry dryer mode",
              "return_type": "VOID",
              "descriptor": "Allows for the control of the laundry dryer mode"
            },
            {
              "service": "SetSpinSpeed",
              "canonical_name": "LaundryDryer_SetSpinSpeed",
              "canonical_name_lower": "laundrydryer_setspinspeed",
              "type": "function",
              "argument_type": "INTEGER",
              "argument_bounds": "Set the spin speed of the laundry dryer",
              "argument_descriptor": "Set the spin speed of the laundry dryer",
              "return_type": "VOID",
              "descriptor": "Allows for the control of the laundry dryer mode"
            },
            {
              "service": "SpinSpeed",
              "canonical_name": "LaundryDryer_SpinSpeed",
              "canonical_name_lower": "laundrydryer_spinspeed",
              "type": "value",
              "return_type": "INTEGER",
              "return_descriptor": "Current spin speed of the laundry dryer",
              "descriptor": "Allows for the control of the laundry dryer mode"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::LeakSensor",
      "source": "service_schema_fallback",
      "categories": [
        "LeakSensor"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "LeakSensor",
          "category_tag": "#LeakSensor",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#LeakSensor)",
            "all(#LeakSensor)"
          ],
          "services": [
            {
              "service": "Leakage",
              "canonical_name": "LeakSensor_Leakage",
              "canonical_name_lower": "leaksensor_leakage",
              "type": "value",
              "return_type": "BOOL",
              "return_descriptor": "Whether or not water leakage was detected by the Device",
              "descriptor": "A Device that senses water leakage"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::LevelControl",
      "source": "service_schema_fallback",
      "categories": [
        "LevelControl"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "LevelControl",
          "category_tag": "#LevelControl",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#LevelControl)",
            "all(#LevelControl)"
          ],
          "services": [
            {
              "service": "CurrentLevel",
              "canonical_name": "LevelControl_CurrentLevel",
              "canonical_name_lower": "levelcontrol_currentlevel",
              "type": "value",
              "return_type": "DOUBLE",
              "return_bounds": [
                0,
                100
              ],
              "return_descriptor": "A number that represents the current level, usually 0-100 in percent",
              "descriptor": "Allows for the control of the level of a device like a light or a dimmer switch"
            },
            {
              "service": "MaxLevel",
              "canonical_name": "LevelControl_MaxLevel",
              "canonical_name_lower": "levelcontrol_maxlevel",
              "type": "value",
              "return_type": "DOUBLE",
              "return_descriptor": "Maximum level the device supports",
              "descriptor": "Allows for the control of the level of a device like a light or a dimmer switch"
            },
            {
              "service": "MinLevel",
              "canonical_name": "LevelControl_MinLevel",
              "canonical_name_lower": "levelcontrol_minlevel",
              "type": "value",
              "return_type": "DOUBLE",
              "return_descriptor": "Minimum level the device supports",
              "descriptor": "Allows for the control of the level of a device like a light or a dimmer switch"
            },
            {
              "service": "MoveToLevel",
              "canonical_name": "LevelControl_MoveToLevel",
              "canonical_name_lower": "levelcontrol_movetolevel",
              "type": "function",
              "argument_type": "DOUBLE | DOUBLE",
              "argument_bounds": "The level value, usually 0-100 in percent, The rate at which to change the level",
              "argument_format": ",",
              "argument_descriptor": "Move the level to the given value. If the device supports being turned on and off then it will be turned on if level is greater than 0 and turned off if level is equal to 0.",
              "return_type": "VOID",
              "descriptor": "Allows for the control of the level of a device like a light or a dimmer switch"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::Light",
      "source": "service_schema_fallback",
      "categories": [
        "Light"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "Light",
          "category_tag": "#Light",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#Light)",
            "all(#Light)"
          ],
          "services": [
            {
              "service": "ColorMode",
              "canonical_name": "Light_ColorMode",
              "canonical_name_lower": "light_colormode",
              "type": "value",
              "return_type": "ENUM",
              "return_descriptor": "Current color mode value",
              "descriptor": "A numerical representation of the brightness intensity",
              "enums": [
                "hsv",
                "rgb",
                "xy",
                "ct"
              ]
            },
            {
              "service": "CurrentBrightness",
              "canonical_name": "Light_CurrentBrightness",
              "canonical_name_lower": "light_currentbrightness",
              "type": "value",
              "return_type": "DOUBLE",
              "return_bounds": [
                0,
                100
              ],
              "return_descriptor": "Current brightness level (0~100%)",
              "descriptor": "A numerical representation of the brightness intensity"
            },
            {
              "service": "CurrentColorTemperature",
              "canonical_name": "Light_CurrentColorTemperature",
              "canonical_name_lower": "light_currentcolortemperature",
              "type": "value",
              "return_type": "INTEGER",
              "return_bounds": [
                0,
                1000000
              ],
              "return_descriptor": "Current color temperature value",
              "descriptor": "A numerical representation of the brightness intensity"
            },
            {
              "service": "CurrentHue",
              "canonical_name": "Light_CurrentHue",
              "canonical_name_lower": "light_currenthue",
              "type": "value",
              "return_type": "DOUBLE",
              "return_bounds": [
                0,
                360
              ],
              "return_descriptor": "Current Hue value",
              "descriptor": "A numerical representation of the brightness intensity"
            },
            {
              "service": "CurrentRGB",
              "canonical_name": "Light_CurrentRGB",
              "canonical_name_lower": "light_currentrgb",
              "type": "value",
              "return_type": "STRING",
              "return_descriptor": "Current RGB value",
              "descriptor": "A numerical representation of the brightness intensity"
            },
            {
              "service": "CurrentSaturation",
              "canonical_name": "Light_CurrentSaturation",
              "canonical_name_lower": "light_currentsaturation",
              "type": "value",
              "return_type": "DOUBLE",
              "return_bounds": [
                0,
                100
              ],
              "return_descriptor": "Current Saturation value",
              "descriptor": "A numerical representation of the brightness intensity"
            },
            {
              "service": "CurrentX",
              "canonical_name": "Light_CurrentX",
              "canonical_name_lower": "light_currentx",
              "type": "value",
              "return_type": "DOUBLE",
              "return_bounds": [
                0,
                1
              ],
              "return_descriptor": "Current X value",
              "descriptor": "A numerical representation of the brightness intensity"
            },
            {
              "service": "CurrentY",
              "canonical_name": "Light_CurrentY",
              "canonical_name_lower": "light_currenty",
              "type": "value",
              "return_type": "DOUBLE",
              "return_bounds": [
                0,
                1
              ],
              "return_descriptor": "Current Y value",
              "descriptor": "A numerical representation of the brightness intensity"
            },
            {
              "service": "MoveToBrightness",
              "canonical_name": "Light_MoveToBrightness",
              "canonical_name_lower": "light_movetobrightness",
              "type": "function",
              "argument_type": "DOUBLE | DOUBLE",
              "argument_bounds": "The brightness value, usually 0-100 in percent, The rate at which to change the brightness",
              "argument_format": ",",
              "argument_descriptor": "Move the Brightness to the given value. If the device supports being turned on and off then it will be turned on if brightness is greater than 0 and turned off if brightness is equal to 0.",
              "return_type": "VOID",
              "descriptor": "A numerical representation of the brightness intensity"
            },
            {
              "service": "MoveToColorTemperature",
              "canonical_name": "Light_MoveToColorTemperature",
              "canonical_name_lower": "light_movetocolortemperature",
              "type": "function",
              "argument_type": "INTEGER",
              "argument_bounds": "color temperature value",
              "argument_descriptor": "Gradually change to the set color temperature",
              "return_type": "VOID",
              "descriptor": "A numerical representation of the brightness intensity"
            },
            {
              "service": "MoveToHue",
              "canonical_name": "Light_MoveToHue",
              "canonical_name_lower": "light_movetohue",
              "type": "function",
              "argument_type": "DOUBLE",
              "argument_bounds": "Hue value to change to",
              "argument_descriptor": "Gradually change to the set Hue",
              "return_type": "VOID",
              "descriptor": "A numerical representation of the brightness intensity"
            },
            {
              "service": "MoveToHueAndSaturation",
              "canonical_name": "Light_MoveToHueAndSaturation",
              "canonical_name_lower": "light_movetohueandsaturation",
              "type": "function",
              "argument_type": "DOUBLE | DOUBLE",
              "argument_bounds": "hue value, saturation value",
              "argument_format": ",",
              "argument_descriptor": "Gradually change to the set Hue and Saturation",
              "return_type": "VOID",
              "descriptor": "A numerical representation of the brightness intensity"
            },
            {
              "service": "MoveToRGB",
              "canonical_name": "Light_MoveToRGB",
              "canonical_name_lower": "light_movetorgb",
              "type": "function",
              "argument_type": "INTEGER | INTEGER | INTEGER",
              "argument_bounds": "red value, green value, blue value",
              "argument_format": ",",
              "argument_descriptor": "Gradually change to the set RGB",
              "return_type": "VOID",
              "descriptor": "A numerical representation of the brightness intensity"
            },
            {
              "service": "MoveToSaturation",
              "canonical_name": "Light_MoveToSaturation",
              "canonical_name_lower": "light_movetosaturation",
              "type": "function",
              "argument_type": "DOUBLE",
              "argument_bounds": "saturation value",
              "argument_descriptor": "Gradually change to the set Saturation",
              "return_type": "VOID",
              "descriptor": "A numerical representation of the brightness intensity"
            },
            {
              "service": "MoveToXY",
              "canonical_name": "Light_MoveToXY",
              "canonical_name_lower": "light_movetoxy",
              "type": "function",
              "argument_type": "DOUBLE | DOUBLE",
              "argument_bounds": "color X value, color Y value",
              "argument_format": ",",
              "argument_descriptor": "Gradually change to the set XY",
              "return_type": "VOID",
              "descriptor": "A numerical representation of the brightness intensity"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::LightSensor",
      "source": "service_schema_fallback",
      "categories": [
        "LightSensor"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "LightSensor",
          "category_tag": "#LightSensor",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#LightSensor)",
            "all(#LightSensor)"
          ],
          "services": [
            {
              "service": "Brightness",
              "canonical_name": "LightSensor_Brightness",
              "canonical_name_lower": "lightsensor_brightness",
              "type": "value",
              "return_type": "DOUBLE",
              "return_descriptor": "brightness intensity (Unit: lux)",
              "descriptor": "A numerical representation of the brightness intensity"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::MenuProvider",
      "source": "service_schema_fallback",
      "categories": [
        "MenuProvider"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "MenuProvider",
          "category_tag": "#MenuProvider",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#MenuProvider)",
            "all(#MenuProvider)"
          ],
          "services": [
            {
              "service": "GetMenu",
              "canonical_name": "MenuProvider_GetMenu",
              "canonical_name_lower": "menuprovider_getmenu",
              "type": "function",
              "argument_type": "STRING",
              "argument_bounds": "The command to get the menu - format: [오늘|내일] [학생식당|수의대식당|전망대(3식당)|예술계식당(아름드리)|기숙사식당|아워홈|동원관식당(113동)|웰스토리(220동)|투굿(공대간이식당)|자하연식당|301동식당] [아침|점심|저녁]",
              "argument_descriptor": "Get the menu - Return the menu list",
              "return_type": "STRING",
              "descriptor": "Provides menu information services"
            },
            {
              "service": "Menu",
              "canonical_name": "MenuProvider_Menu",
              "canonical_name_lower": "menuprovider_menu",
              "type": "value",
              "return_type": "STRING",
              "return_descriptor": "Current menu information",
              "descriptor": "Provides menu information services"
            },
            {
              "service": "TodayMenu",
              "canonical_name": "MenuProvider_TodayMenu",
              "canonical_name_lower": "menuprovider_todaymenu",
              "type": "value",
              "return_type": "STRING",
              "return_descriptor": "Today's menu",
              "descriptor": "Provides menu information services"
            },
            {
              "service": "TodayPlace",
              "canonical_name": "MenuProvider_TodayPlace",
              "canonical_name_lower": "menuprovider_todayplace",
              "type": "value",
              "return_type": "STRING",
              "return_descriptor": "Today's place",
              "descriptor": "Provides menu information services"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::MotionSensor",
      "source": "service_schema_fallback",
      "categories": [
        "MotionSensor"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "MotionSensor",
          "category_tag": "#MotionSensor",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#MotionSensor)",
            "all(#MotionSensor)"
          ],
          "services": [
            {
              "service": "Motion",
              "canonical_name": "MotionSensor_Motion",
              "canonical_name_lower": "motionsensor_motion",
              "type": "value",
              "return_type": "BOOL",
              "return_descriptor": "The current state of the motion sensor",
              "descriptor": "Motion sensor device"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::Oven",
      "source": "service_schema_fallback",
      "categories": [
        "Oven"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "Oven",
          "category_tag": "#Oven",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#Oven)",
            "all(#Oven)"
          ],
          "services": [
            {
              "service": "AddMoreTime",
              "canonical_name": "Oven_AddMoreTime",
              "canonical_name_lower": "oven_addmoretime",
              "type": "function",
              "argument_type": "DOUBLE",
              "argument_bounds": "Set the additional cooking time of the oven",
              "argument_descriptor": "Add more time to the current cooking process of the oven",
              "return_type": "VOID",
              "descriptor": "Allows for the control of the oven mode"
            },
            {
              "service": "OvenMode",
              "canonical_name": "Oven_OvenMode",
              "canonical_name_lower": "oven_ovenmode",
              "type": "value",
              "return_type": "ENUM",
              "return_descriptor": "Current mode of the oven",
              "descriptor": "Allows for the control of the oven mode",
              "enums": [
                "heating",
                "grill",
                "warming",
                "defrosting",
                "Conventional",
                "Bake",
                "BottomHeat",
                "ConvectionBake",
                "ConvectionRoast",
                "Broil",
                "ConvectionBroil",
                "SteamCook",
                "SteamBake",
                "SteamRoast",
                "SteamBottomHeatplusConvection",
                "Microwave",
                "MWplusGrill",
                "MWplusConvection",
                "MWplusHotBlast",
                "MWplusHotBlast2",
                "SlimMiddle",
                "SlimStrong",
                "SlowCook",
                "Proof",
                "Dehydrate",
                "Others",
                "StrongSteam",
                "Descale",
                "Rinse"
              ]
            },
            {
              "service": "SetCookingParameters",
              "canonical_name": "Oven_SetCookingParameters",
              "canonical_name_lower": "oven_setcookingparameters",
              "type": "function",
              "argument_type": "ENUM | DOUBLE",
              "argument_bounds": "Set the mode of the oven, Set the cooking time of the oven in seconds",
              "argument_format": ",",
              "argument_descriptor": "Set the cooking parameters of the oven",
              "return_type": "VOID",
              "descriptor": "Allows for the control of the oven mode"
            },
            {
              "service": "SetOvenMode",
              "canonical_name": "Oven_SetOvenMode",
              "canonical_name_lower": "oven_setovenmode",
              "type": "function",
              "argument_type": "ENUM",
              "argument_bounds": "Set the oven mode",
              "argument_descriptor": "Set the oven mode",
              "return_type": "VOID",
              "descriptor": "Allows for the control of the oven mode"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::Plug",
      "source": "service_schema_fallback",
      "categories": [
        "Plug"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "Plug",
          "category_tag": "#Plug",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#Plug)",
            "all(#Plug)"
          ],
          "services": [
            {
              "service": "Current",
              "canonical_name": "Plug_Current",
              "canonical_name_lower": "plug_current",
              "type": "value",
              "return_type": "DOUBLE",
              "return_descriptor": "The current flowing into or out of the battery in amperes",
              "descriptor": "Allows for monitoring power consumption of a plug device"
            },
            {
              "service": "Power",
              "canonical_name": "Plug_Power",
              "canonical_name_lower": "plug_power",
              "type": "value",
              "return_type": "DOUBLE",
              "return_descriptor": "The power consumption of the device in watts",
              "descriptor": "Allows for monitoring power consumption of a plug device"
            },
            {
              "service": "Voltage",
              "canonical_name": "Plug_Voltage",
              "canonical_name_lower": "plug_voltage",
              "type": "value",
              "return_type": "DOUBLE",
              "return_descriptor": "The voltage of the battery in millivolts",
              "descriptor": "Allows for monitoring power consumption of a plug device"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::PresenceSensor",
      "source": "service_schema_fallback",
      "categories": [
        "PresenceSensor"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "PresenceSensor",
          "category_tag": "#PresenceSensor",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#PresenceSensor)",
            "all(#PresenceSensor)"
          ],
          "services": [
            {
              "service": "Presence",
              "canonical_name": "PresenceSensor_Presence",
              "canonical_name_lower": "presencesensor_presence",
              "type": "value",
              "return_type": "BOOL",
              "return_descriptor": "The current state of the presence sensor",
              "descriptor": "The ability to see the current status of a presence sensor device"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::PresenceVitalSensor",
      "source": "service_schema_fallback",
      "categories": [
        "PresenceVitalSensor"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "PresenceVitalSensor",
          "category_tag": "#PresenceVitalSensor",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#PresenceVitalSensor)",
            "all(#PresenceVitalSensor)"
          ],
          "services": [
            {
              "service": "Awakeness",
              "canonical_name": "PresenceVitalSensor_Awakeness",
              "canonical_name_lower": "presencevitalsensor_awakeness",
              "type": "value",
              "return_type": "DOUBLE",
              "return_bounds": [
                -10,
                10
              ],
              "return_descriptor": "Sleep/wake status indicator",
              "descriptor": "Presence and vital signs sensor with heart rate, respiratory rate, movement detection"
            },
            {
              "service": "Distance",
              "canonical_name": "PresenceVitalSensor_Distance",
              "canonical_name_lower": "presencevitalsensor_distance",
              "type": "value",
              "return_type": "DOUBLE",
              "return_bounds": [
                0,
                10
              ],
              "return_descriptor": "Distance at which the subject is detected in meters",
              "descriptor": "Presence and vital signs sensor with heart rate, respiratory rate, movement detection"
            },
            {
              "service": "DwellTime",
              "canonical_name": "PresenceVitalSensor_DwellTime",
              "canonical_name_lower": "presencevitalsensor_dwelltime",
              "type": "value",
              "return_type": "DOUBLE",
              "return_bounds": [
                0,
                100000
              ],
              "return_descriptor": "Time duration the subject has been present in seconds",
              "descriptor": "Presence and vital signs sensor with heart rate, respiratory rate, movement detection"
            },
            {
              "service": "HeartRate",
              "canonical_name": "PresenceVitalSensor_HeartRate",
              "canonical_name_lower": "presencevitalsensor_heartrate",
              "type": "value",
              "return_type": "DOUBLE",
              "return_bounds": [
                0,
                250
              ],
              "return_descriptor": "Heart rate in beats per minute",
              "descriptor": "Presence and vital signs sensor with heart rate, respiratory rate, movement detection"
            },
            {
              "service": "MovementIndex",
              "canonical_name": "PresenceVitalSensor_MovementIndex",
              "canonical_name_lower": "presencevitalsensor_movementindex",
              "type": "value",
              "return_type": "DOUBLE",
              "return_bounds": [
                0,
                100
              ],
              "return_descriptor": "Intensity of detected relative movement",
              "descriptor": "Presence and vital signs sensor with heart rate, respiratory rate, movement detection"
            },
            {
              "service": "Presence",
              "canonical_name": "PresenceVitalSensor_Presence",
              "canonical_name_lower": "presencevitalsensor_presence",
              "type": "value",
              "return_type": "BOOL",
              "return_descriptor": "Presence detection status",
              "descriptor": "Presence and vital signs sensor with heart rate, respiratory rate, movement detection"
            },
            {
              "service": "RespiratoryRate",
              "canonical_name": "PresenceVitalSensor_RespiratoryRate",
              "canonical_name_lower": "presencevitalsensor_respiratoryrate",
              "type": "value",
              "return_type": "DOUBLE",
              "return_bounds": [
                0,
                60
              ],
              "return_descriptor": "Respiratory rate in breaths per minute",
              "descriptor": "Presence and vital signs sensor with heart rate, respiratory rate, movement detection"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::PressureSensor",
      "source": "service_schema_fallback",
      "categories": [
        "PressureSensor"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "PressureSensor",
          "category_tag": "#PressureSensor",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#PressureSensor)",
            "all(#PressureSensor)"
          ],
          "services": [
            {
              "service": "Pressure",
              "canonical_name": "PressureSensor_Pressure",
              "canonical_name_lower": "pressuresensor_pressure",
              "type": "value",
              "return_type": "DOUBLE",
              "return_descriptor": "The current state of the pressure sensor",
              "descriptor": "The ability to see the current status of a pressure sensor device"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::Pump",
      "source": "service_schema_fallback",
      "categories": [
        "Pump"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "Pump",
          "category_tag": "#Pump",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#Pump)",
            "all(#Pump)"
          ],
          "services": [
            {
              "service": "PumpMode",
              "canonical_name": "Pump_PumpMode",
              "canonical_name_lower": "pump_pumpmode",
              "type": "value",
              "return_type": "ENUM",
              "return_descriptor": "A string representation of whether the Pump is normal, minimum, maximum, or localSetting",
              "descriptor": "Allows for the control of a pump device",
              "enums": [
                "normal",
                "minimum",
                "maximum",
                "localSetting"
              ]
            },
            {
              "service": "SetPumpMode",
              "canonical_name": "Pump_SetPumpMode",
              "canonical_name_lower": "pump_setpumpmode",
              "type": "function",
              "argument_type": "ENUM",
              "argument_bounds": "The desired Pump mode",
              "argument_descriptor": "Set the Pump mode",
              "return_type": "VOID",
              "descriptor": "Allows for the control of a pump device"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::RainSensor",
      "source": "service_schema_fallback",
      "categories": [
        "RainSensor"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "RainSensor",
          "category_tag": "#RainSensor",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#RainSensor)",
            "all(#RainSensor)"
          ],
          "services": [
            {
              "service": "Rain",
              "canonical_name": "RainSensor_Rain",
              "canonical_name_lower": "rainsensor_rain",
              "type": "value",
              "return_type": "BOOL",
              "return_descriptor": "The current state of the rain sensor",
              "descriptor": "A Device that senses rain"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::RiceCooker",
      "source": "service_schema_fallback",
      "categories": [
        "RiceCooker"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "RiceCooker",
          "category_tag": "#RiceCooker",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#RiceCooker)",
            "all(#RiceCooker)"
          ],
          "services": [
            {
              "service": "AddMoreTime",
              "canonical_name": "RiceCooker_AddMoreTime",
              "canonical_name_lower": "ricecooker_addmoretime",
              "type": "function",
              "argument_type": "DOUBLE",
              "argument_bounds": "The additional time to add to the Rice Cooker",
              "argument_descriptor": "Add more time to the Rice Cooker",
              "return_type": "VOID",
              "descriptor": "Allows for the control of the Rice Cooker"
            },
            {
              "service": "RiceCookerMode",
              "canonical_name": "RiceCooker_RiceCookerMode",
              "canonical_name_lower": "ricecooker_ricecookermode",
              "type": "value",
              "return_type": "ENUM",
              "return_descriptor": "Current mode of the rice cooker",
              "descriptor": "Allows for the control of the Rice Cooker",
              "enums": [
                "cooking",
                "keepWarm",
                "reheating",
                "autoClean",
                "soakInnerPot"
              ]
            },
            {
              "service": "SetCookingParameters",
              "canonical_name": "RiceCooker_SetCookingParameters",
              "canonical_name_lower": "ricecooker_setcookingparameters",
              "type": "function",
              "argument_type": "ENUM | DOUBLE",
              "argument_bounds": "The desired Rice Cooker mode, The cooking time in seconds",
              "argument_format": ",",
              "argument_descriptor": "Set the cooking parameters for the Rice Cooker",
              "return_type": "VOID",
              "descriptor": "Allows for the control of the Rice Cooker"
            },
            {
              "service": "SetRiceCookerMode",
              "canonical_name": "RiceCooker_SetRiceCookerMode",
              "canonical_name_lower": "ricecooker_setricecookermode",
              "type": "function",
              "argument_type": "ENUM",
              "argument_bounds": "The desired Rice Cooker mode",
              "argument_descriptor": "Set the Rice Cooker mode",
              "return_type": "VOID",
              "descriptor": "Allows for the control of the Rice Cooker"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::RobotVacuumCleaner",
      "source": "service_schema_fallback",
      "categories": [
        "RobotVacuumCleaner"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "RobotVacuumCleaner",
          "category_tag": "#RobotVacuumCleaner",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#RobotVacuumCleaner)",
            "all(#RobotVacuumCleaner)"
          ],
          "services": [
            {
              "service": "RobotVacuumCleanerMode",
              "canonical_name": "RobotVacuumCleaner_RobotVacuumCleanerMode",
              "canonical_name_lower": "robotvacuumcleaner_robotvacuumcleanermode",
              "type": "value",
              "return_type": "ENUM",
              "return_descriptor": "Current status of the robot cleaner cleaning mode",
              "descriptor": "Allows for the control of the robot cleaner cleaning mode",
              "enums": [
                "auto",
                "part",
                "repeat",
                "manual",
                "stop",
                "map"
              ]
            },
            {
              "service": "SetRobotVacuumCleanerModeMode",
              "canonical_name": "RobotVacuumCleaner_SetRobotVacuumCleanerModeMode",
              "canonical_name_lower": "robotvacuumcleaner_setrobotvacuumcleanermodemode",
              "type": "function",
              "argument_type": "ENUM",
              "argument_bounds": "Set the robot cleaner cleaning mode, to \"auto\", \"part\", \"repeat\", \"manual\" or \"stop\" modes",
              "argument_descriptor": "Set the robot cleaner cleaning mode",
              "return_type": "VOID",
              "descriptor": "Allows for the control of the robot cleaner cleaning mode"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::Safe",
      "source": "service_schema_fallback",
      "categories": [
        "Safe"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "Safe",
          "category_tag": "#Safe",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#Safe)",
            "all(#Safe)"
          ],
          "services": [
            {
              "service": "Lock",
              "canonical_name": "Safe_Lock",
              "canonical_name_lower": "safe_lock",
              "type": "function",
              "argument_descriptor": "Lock the Safe",
              "return_type": "VOID",
              "descriptor": "Allows for the control of the Safe"
            },
            {
              "service": "SafeState",
              "canonical_name": "Safe_SafeState",
              "canonical_name_lower": "safe_safestate",
              "type": "value",
              "return_type": "ENUM",
              "return_descriptor": "Current Safe state",
              "descriptor": "Allows for the control of the Safe",
              "enums": [
                "closed",
                "closing",
                "open",
                "opening",
                "unknown"
              ]
            },
            {
              "service": "Unlock",
              "canonical_name": "Safe_Unlock",
              "canonical_name_lower": "safe_unlock",
              "type": "function",
              "argument_descriptor": "Unlock the Safe",
              "return_type": "VOID",
              "descriptor": "Allows for the control of the Safe"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::Siren",
      "source": "service_schema_fallback",
      "categories": [
        "Siren"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "Siren",
          "category_tag": "#Siren",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#Siren)",
            "all(#Siren)"
          ],
          "services": [
            {
              "service": "SetSirenMode",
              "canonical_name": "Siren_SetSirenMode",
              "canonical_name_lower": "siren_setsirenmode",
              "type": "function",
              "argument_type": "ENUM",
              "argument_bounds": "Set the Siren mode",
              "argument_descriptor": "Set the Siren mode",
              "return_type": "VOID",
              "descriptor": "Allows for the control of the Siren"
            },
            {
              "service": "SirenMode",
              "canonical_name": "Siren_SirenMode",
              "canonical_name_lower": "siren_sirenmode",
              "type": "value",
              "return_type": "ENUM",
              "return_descriptor": "Current Siren mode",
              "descriptor": "Allows for the control of the Siren",
              "enums": [
                "emergency",
                "fire",
                "police",
                "ambulance"
              ]
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::SmokeDetector",
      "source": "service_schema_fallback",
      "categories": [
        "SmokeDetector"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "SmokeDetector",
          "category_tag": "#SmokeDetector",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#SmokeDetector)",
            "all(#SmokeDetector)"
          ],
          "services": [
            {
              "service": "Smoke",
              "canonical_name": "SmokeDetector_Smoke",
              "canonical_name_lower": "smokedetector_smoke",
              "type": "value",
              "return_type": "BOOL",
              "return_descriptor": "The state of the smoke detection device",
              "descriptor": "A Device that detects smoke"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::SoundSensor",
      "source": "service_schema_fallback",
      "categories": [
        "SoundSensor"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "SoundSensor",
          "category_tag": "#SoundSensor",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#SoundSensor)",
            "all(#SoundSensor)"
          ],
          "services": [
            {
              "service": "Sound",
              "canonical_name": "SoundSensor_Sound",
              "canonical_name_lower": "soundsensor_sound",
              "type": "value",
              "return_type": "DOUBLE",
              "return_descriptor": "Sound level measurement as a numerical value",
              "descriptor": "Sound sensor device for measuring sound levels"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::Speaker",
      "source": "service_schema_fallback",
      "categories": [
        "Speaker"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "Speaker",
          "category_tag": "#Speaker",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#Speaker)",
            "all(#Speaker)"
          ],
          "services": [
            {
              "service": "FastForward",
              "canonical_name": "Speaker_FastForward",
              "canonical_name_lower": "speaker_fastforward",
              "type": "function",
              "argument_descriptor": "Fast forward media playback",
              "return_type": "VOID",
              "descriptor": "Speaker device for audio playback and media control"
            },
            {
              "service": "Pause",
              "canonical_name": "Speaker_Pause",
              "canonical_name_lower": "speaker_pause",
              "type": "function",
              "argument_descriptor": "Pause media playback",
              "return_type": "VOID",
              "descriptor": "Speaker device for audio playback and media control"
            },
            {
              "service": "Play",
              "canonical_name": "Speaker_Play",
              "canonical_name_lower": "speaker_play",
              "type": "function",
              "argument_type": "STRING",
              "argument_bounds": "Media source to play (e.g., URL or file path)",
              "argument_descriptor": "Start media playback",
              "return_type": "VOID",
              "descriptor": "Speaker device for audio playback and media control"
            },
            {
              "service": "PlaybackState",
              "canonical_name": "Speaker_PlaybackState",
              "canonical_name_lower": "speaker_playbackstate",
              "type": "value",
              "return_type": "ENUM",
              "return_descriptor": "Current playback status",
              "descriptor": "Speaker device for audio playback and media control",
              "enums": [
                "paused",
                "playing",
                "stopped",
                "fastforwarding",
                "rewinding",
                "buffering"
              ]
            },
            {
              "service": "Rewind",
              "canonical_name": "Speaker_Rewind",
              "canonical_name_lower": "speaker_rewind",
              "type": "function",
              "argument_descriptor": "Rewind media playback",
              "return_type": "VOID",
              "descriptor": "Speaker device for audio playback and media control"
            },
            {
              "service": "SetVolume",
              "canonical_name": "Speaker_SetVolume",
              "canonical_name_lower": "speaker_setvolume",
              "type": "function",
              "argument_type": "INTEGER",
              "argument_bounds": "Volume level to set (0-100)",
              "argument_descriptor": "Set the speaker volume level. Returns the new volume level.",
              "return_type": "INTEGER",
              "descriptor": "Speaker device for audio playback and media control"
            },
            {
              "service": "Speak",
              "canonical_name": "Speaker_Speak",
              "canonical_name_lower": "speaker_speak",
              "type": "function",
              "argument_type": "STRING",
              "argument_bounds": "Text to speak",
              "argument_descriptor": "Speak a text string",
              "return_type": "VOID",
              "descriptor": "Speaker device for audio playback and media control"
            },
            {
              "service": "Stop",
              "canonical_name": "Speaker_Stop",
              "canonical_name_lower": "speaker_stop",
              "type": "function",
              "argument_descriptor": "Stop media playback",
              "return_type": "VOID",
              "descriptor": "Speaker device for audio playback and media control"
            },
            {
              "service": "Volume",
              "canonical_name": "Speaker_Volume",
              "canonical_name_lower": "speaker_volume",
              "type": "value",
              "return_type": "INTEGER",
              "return_bounds": [
                0,
                100
              ],
              "return_descriptor": "Current volume level",
              "descriptor": "Speaker device for audio playback and media control"
            },
            {
              "service": "VolumeDown",
              "canonical_name": "Speaker_VolumeDown",
              "canonical_name_lower": "speaker_volumedown",
              "type": "function",
              "argument_descriptor": "Set the speaker volume level. Return the new volume level",
              "return_type": "INTEGER",
              "descriptor": "Speaker device for audio playback and media control"
            },
            {
              "service": "VolumeUp",
              "canonical_name": "Speaker_VolumeUp",
              "canonical_name_lower": "speaker_volumeup",
              "type": "function",
              "argument_descriptor": "Set the speaker volume level. Return the new volume level",
              "return_type": "INTEGER",
              "descriptor": "Speaker device for audio playback and media control"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::Switch",
      "source": "service_schema_fallback",
      "categories": [
        "Switch"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "Switch",
          "category_tag": "#Switch",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#Switch)",
            "all(#Switch)"
          ],
          "services": [
            {
              "service": "Off",
              "canonical_name": "Switch_Off",
              "canonical_name_lower": "switch_off",
              "type": "function",
              "argument_descriptor": "Turn a Switch off",
              "return_type": "VOID",
              "descriptor": "Allows for the control of a Switch device"
            },
            {
              "service": "On",
              "canonical_name": "Switch_On",
              "canonical_name_lower": "switch_on",
              "type": "function",
              "argument_descriptor": "Turn a Switch on",
              "return_type": "VOID",
              "descriptor": "Allows for the control of a Switch device"
            },
            {
              "service": "Switch",
              "canonical_name": "Switch_Switch",
              "canonical_name_lower": "switch_switch",
              "type": "value",
              "return_type": "BOOL",
              "return_descriptor": "The state of the Switch device",
              "descriptor": "Allows for the control of a Switch device"
            },
            {
              "service": "Toggle",
              "canonical_name": "Switch_Toggle",
              "canonical_name_lower": "switch_toggle",
              "type": "function",
              "argument_descriptor": "Toggle a Switch. Returns the new state of the Switch.",
              "return_type": "BOOL",
              "descriptor": "Allows for the control of a Switch device"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::TapDialSwitch",
      "source": "service_schema_fallback",
      "categories": [
        "TapDialSwitch"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "TapDialSwitch",
          "category_tag": "#TapDialSwitch",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#TapDialSwitch)",
            "all(#TapDialSwitch)"
          ],
          "services": [
            {
              "service": "Button1",
              "canonical_name": "TapDialSwitch_Button1",
              "canonical_name_lower": "tapdialswitch_button1",
              "type": "value",
              "return_type": "ENUM",
              "return_descriptor": "Button 1 state",
              "descriptor": "A tap dial switch device with multiple buttons and a rotary dial",
              "enums": [
                "pushed",
                "held",
                "double",
                "pushed_2x",
                "pushed_3x",
                "down",
                "down_hold",
                "up",
                "up_hold"
              ]
            },
            {
              "service": "Button2",
              "canonical_name": "TapDialSwitch_Button2",
              "canonical_name_lower": "tapdialswitch_button2",
              "type": "value",
              "return_type": "ENUM",
              "return_descriptor": "Button 2 state",
              "descriptor": "A tap dial switch device with multiple buttons and a rotary dial"
            },
            {
              "service": "Button3",
              "canonical_name": "TapDialSwitch_Button3",
              "canonical_name_lower": "tapdialswitch_button3",
              "type": "value",
              "return_type": "ENUM",
              "return_descriptor": "Button 3 state",
              "descriptor": "A tap dial switch device with multiple buttons and a rotary dial"
            },
            {
              "service": "Button4",
              "canonical_name": "TapDialSwitch_Button4",
              "canonical_name_lower": "tapdialswitch_button4",
              "type": "value",
              "return_type": "ENUM",
              "return_descriptor": "Button 4 state",
              "descriptor": "A tap dial switch device with multiple buttons and a rotary dial"
            },
            {
              "service": "Rotation",
              "canonical_name": "TapDialSwitch_Rotation",
              "canonical_name_lower": "tapdialswitch_rotation",
              "type": "value",
              "return_type": "ENUM",
              "return_descriptor": "Rotary control state (direction)",
              "descriptor": "A tap dial switch device with multiple buttons and a rotary dial",
              "enums": [
                "clockwise",
                "counter_clockwise"
              ]
            },
            {
              "service": "RotationSteps",
              "canonical_name": "TapDialSwitch_RotationSteps",
              "canonical_name_lower": "tapdialswitch_rotationsteps",
              "type": "value",
              "return_type": "INTEGER",
              "return_bounds": [
                -100,
                100
              ],
              "return_descriptor": "Number of rotation steps",
              "descriptor": "A tap dial switch device with multiple buttons and a rotary dial"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::Television",
      "source": "service_schema_fallback",
      "categories": [
        "Television"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "Television",
          "category_tag": "#Television",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#Television)",
            "all(#Television)"
          ],
          "services": [
            {
              "service": "Channel",
              "canonical_name": "Television_Channel",
              "canonical_name_lower": "television_channel",
              "type": "value",
              "return_type": "INTEGER",
              "return_bounds": [
                0,
                10000
              ],
              "return_descriptor": "The current channel",
              "descriptor": "A television device"
            },
            {
              "service": "ChannelDown",
              "canonical_name": "Television_ChannelDown",
              "canonical_name_lower": "television_channeldown",
              "type": "function",
              "argument_descriptor": "Change the channel down",
              "return_type": "INTEGER",
              "descriptor": "A television device"
            },
            {
              "service": "ChannelUp",
              "canonical_name": "Television_ChannelUp",
              "canonical_name_lower": "television_channelup",
              "type": "function",
              "argument_descriptor": "Change the channel up",
              "return_type": "INTEGER",
              "descriptor": "A television device"
            },
            {
              "service": "SetChannel",
              "canonical_name": "Television_SetChannel",
              "canonical_name_lower": "television_setchannel",
              "type": "function",
              "argument_type": "INTEGER",
              "argument_bounds": "Set the current channel (0-10000)",
              "argument_descriptor": "Set the current channel",
              "return_type": "VOID",
              "descriptor": "A television device"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::TemperatureSensor",
      "source": "service_schema_fallback",
      "categories": [
        "TemperatureSensor"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "TemperatureSensor",
          "category_tag": "#TemperatureSensor",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#TemperatureSensor)",
            "all(#TemperatureSensor)"
          ],
          "services": [
            {
              "service": "Temperature",
              "canonical_name": "TemperatureSensor_Temperature",
              "canonical_name_lower": "temperaturesensor_temperature",
              "type": "value",
              "return_type": "DOUBLE",
              "return_bounds": [
                -40,
                60
              ],
              "return_descriptor": "A number that usually represents the current temperature",
              "descriptor": "Get the temperature from a Device that reports current temperature"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::Valve",
      "source": "service_schema_fallback",
      "categories": [
        "Valve"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "Valve",
          "category_tag": "#Valve",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#Valve)",
            "all(#Valve)"
          ],
          "services": [
            {
              "service": "Close",
              "canonical_name": "Valve_Close",
              "canonical_name_lower": "valve_close",
              "type": "function",
              "argument_descriptor": "Close the valve",
              "return_type": "VOID",
              "descriptor": "Controls a valve to open or close it"
            },
            {
              "service": "Open",
              "canonical_name": "Valve_Open",
              "canonical_name_lower": "valve_open",
              "type": "function",
              "argument_descriptor": "Open the valve",
              "return_type": "VOID",
              "descriptor": "Controls a valve to open or close it"
            },
            {
              "service": "ValveState",
              "canonical_name": "Valve_ValveState",
              "canonical_name_lower": "valve_valvestate",
              "type": "value",
              "return_type": "BOOL",
              "return_descriptor": "Current state of the valve",
              "descriptor": "Controls a valve to open or close it"
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::WeatherProvider",
      "source": "service_schema_fallback",
      "categories": [
        "WeatherProvider"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "WeatherProvider",
          "category_tag": "#WeatherProvider",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#WeatherProvider)",
            "all(#WeatherProvider)"
          ],
          "services": [
            {
              "service": "GetWeatherInfo",
              "canonical_name": "WeatherProvider_GetWeatherInfo",
              "canonical_name_lower": "weatherprovider_getweatherinfo",
              "type": "function",
              "argument_type": "DOUBLE | DOUBLE",
              "argument_bounds": "The latitude of the location, The longitude of the location",
              "argument_format": ",",
              "argument_descriptor": "Get the current weather information - Return whole weather information, format: \"temperature, humidity, pressure, pm25, pm10, weather, weather_string, icon_id, location\"",
              "return_type": "STRING",
              "descriptor": "Provides weather information"
            },
            {
              "service": "HumidityWeather",
              "canonical_name": "WeatherProvider_HumidityWeather",
              "canonical_name_lower": "weatherprovider_humidityweather",
              "type": "value",
              "return_type": "DOUBLE",
              "return_bounds": [
                0,
                100
              ],
              "return_descriptor": "Current humidity level",
              "descriptor": "Provides weather information"
            },
            {
              "service": "Pm10Weather",
              "canonical_name": "WeatherProvider_Pm10Weather",
              "canonical_name_lower": "weatherprovider_pm10weather",
              "type": "value",
              "return_type": "DOUBLE",
              "return_bounds": [
                0,
                10000
              ],
              "return_descriptor": "Current pm10 level",
              "descriptor": "Provides weather information"
            },
            {
              "service": "Pm25Weather",
              "canonical_name": "WeatherProvider_Pm25Weather",
              "canonical_name_lower": "weatherprovider_pm25weather",
              "type": "value",
              "return_type": "DOUBLE",
              "return_bounds": [
                0,
                10000
              ],
              "return_descriptor": "Current pm25 level",
              "descriptor": "Provides weather information"
            },
            {
              "service": "PressureWeather",
              "canonical_name": "WeatherProvider_PressureWeather",
              "canonical_name_lower": "weatherprovider_pressureweather",
              "type": "value",
              "return_type": "DOUBLE",
              "return_bounds": [
                0,
                2000
              ],
              "return_descriptor": "Current pressure level",
              "descriptor": "Provides weather information"
            },
            {
              "service": "TemperatureWeather",
              "canonical_name": "WeatherProvider_TemperatureWeather",
              "canonical_name_lower": "weatherprovider_temperatureweather",
              "type": "value",
              "return_type": "DOUBLE",
              "return_bounds": [
                -470,
                10000
              ],
              "return_descriptor": "Current temperature level",
              "descriptor": "Provides weather information"
            },
            {
              "service": "Weather",
              "canonical_name": "WeatherProvider_Weather",
              "canonical_name_lower": "weatherprovider_weather",
              "type": "value",
              "return_type": "ENUM",
              "return_descriptor": "Current weather condition",
              "descriptor": "Provides weather information",
              "enums": [
                "thunderstorm",
                "drizzle",
                "rain",
                "snow",
                "mist",
                "smoke",
                "haze",
                "dust",
                "fog",
                "sand",
                "ash",
                "squall",
                "tornado",
                "clear",
                "clouds"
              ]
            }
          ]
        }
      ]
    },
    {
      "group_id": "schema::WindowCovering",
      "source": "service_schema_fallback",
      "categories": [
        "WindowCovering"
      ],
      "user_defined_tags": [],
      "locations": [],
      "capability_bindings": [
        {
          "category": "WindowCovering",
          "category_tag": "#WindowCovering",
          "user_defined_tags": [],
          "locations": [],
          "selector_tags": [],
          "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)"
          ],
          "receiver_examples": [
            "(#WindowCovering)",
            "all(#WindowCovering)"
          ],
          "services": [
            {
              "service": "CurrentPosition",
              "canonical_name": "WindowCovering_CurrentPosition",
              "canonical_name_lower": "windowcovering_currentposition",
              "type": "value",
              "return_type": "INTEGER",
              "return_descriptor": "Current position of the window covering (0-100)",
              "descriptor": "Controls a window covering to open or close it"
            },
            {
              "service": "DownOrClose",
              "canonical_name": "WindowCovering_DownOrClose",
              "canonical_name_lower": "windowcovering_downorclose",
              "type": "function",
              "argument_descriptor": "Down or close the window",
              "return_type": "VOID",
              "descriptor": "Controls a window covering to open or close it"
            },
            {
              "service": "SetLevel",
              "canonical_name": "WindowCovering_SetLevel",
              "canonical_name_lower": "windowcovering_setlevel",
              "type": "function",
              "argument_type": "INTEGER",
              "argument_bounds": "Level to set the window covering to (0-100)",
              "argument_descriptor": "Set the level of the window covering (0-100). Return the level set.",
              "return_type": "INTEGER",
              "descriptor": "Controls a window covering to open or close it"
            },
            {
              "service": "Stop",
              "canonical_name": "WindowCovering_Stop",
              "canonical_name_lower": "windowcovering_stop",
              "type": "function",
              "argument_descriptor": "Stop the window covering",
              "return_type": "VOID",
              "descriptor": "Controls a window covering to open or close it"
            },
            {
              "service": "UpOrOpen",
              "canonical_name": "WindowCovering_UpOrOpen",
              "canonical_name_lower": "windowcovering_uporopen",
              "type": "function",
              "argument_descriptor": "Up or open the window",
              "return_type": "VOID",
              "descriptor": "Controls a window covering to open or close it"
            },
            {
              "service": "WindowCoveringType",
              "canonical_name": "WindowCovering_WindowCoveringType",
              "canonical_name_lower": "windowcovering_windowcoveringtype",
              "type": "value",
              "return_type": "ENUM",
              "return_descriptor": "Type of window covering",
              "descriptor": "Controls a window covering to open or close it",
              "enums": [
                "window",
                "blind",
                "shade"
              ]
            }
          ]
        }
      ]
    }
  ]
}

How to read the snippet:
