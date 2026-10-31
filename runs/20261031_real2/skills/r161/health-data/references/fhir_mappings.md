# FHIR R4 Mappings for Apple Health Data

## LOINC Code Mappings

| Apple Health Type | LOINC Code | Display Name | UCUM Unit |
|-------------------|------------|--------------|-----------|
| HKQuantityTypeIdentifierHeartRate | 8867-4 | Heart rate | /min |
| HKQuantityTypeIdentifierHeartRateVariabilitySDNN | 80404-7 | R-R interval.standard deviation | ms |
| HKQuantityTypeIdentifierRestingHeartRate | 40443-4 | Resting heart rate | /min |
| HKQuantityTypeIdentifierWalkingHeartRateAverage | 89270-3 | Walking heart rate | /min |
| HKQuantityTypeIdentifierOxygenSaturation | 59408-5 | Oxygen saturation in Arterial blood by Pulse oximetry | % |
| HKQuantityTypeIdentifierRespiratoryRate | 9279-1 | Respiratory rate | /min |
| HKQuantityTypeIdentifierBodyTemperature | 8310-5 | Body temperature | Cel |
| HKQuantityTypeIdentifierBloodPressureSystolic | 8480-6 | Systolic blood pressure | mm[Hg] |
| HKQuantityTypeIdentifierBloodPressureDiastolic | 8462-4 | Diastolic blood pressure | mm[Hg] |
| HKQuantityTypeIdentifierBodyMass | 29463-7 | Body weight | kg |
| HKQuantityTypeIdentifierHeight | 8302-2 | Body height | cm |
| HKQuantityTypeIdentifierBodyMassIndex | 39156-5 | Body mass index | kg/m2 |
| HKQuantityTypeIdentifierStepCount | 55423-8 | Number of steps in unspecified time Pedometer | {steps} |
| HKQuantityTypeIdentifierDistanceWalkingRunning | 41953-1 | Walking distance | km |
| HKQuantityTypeIdentifierActiveEnergyBurned | 41981-2 | Calories burned | kcal |
| HKQuantityTypeIdentifierFlightsClimbed | 93831-6 | Flights of stairs climbed | {flights} |
| HKQuantityTypeIdentifierVO2Max | 60842-2 | Oxygen consumption (VO2 max) | mL/min/kg |
| HKCategoryTypeIdentifierSleepAnalysis | 93832-4 | Sleep duration | h |

## FHIR Observation Categories

| Category Code | Display | Used For |
|---------------|---------|----------|
| vital-signs | Vital Signs | HR, SpO2, BP, Temp, RR |
| activity | Activity | Steps, Distance, Calories, Exercise |
| sleep-wake | Sleep/Wake | Sleep analysis |

## FHIR R4 Observation Template

```json
{
  "resourceType": "Observation",
  "id": "<uuid>",
  "meta": {
    "profile": ["[url-1]"]
  },
  "status": "final",
  "category": [{
    "coding": [{
      "system": "[url-2]",
      "code": "vital-signs",
      "display": "Vital Signs"
    }]
  }],
  "code": {
    "coding": [{
      "system": "[url-3]",
      "code": "<LOINC_CODE>",
      "display": "<DISPLAY_NAME>"
    }],
    "text": "<FRIENDLY_NAME>"
  },
  "subject": {
    "reference": "Patient/self"
  },
  "effectiveDateTime": "<ISO_TIMESTAMP>",
  "valueQuantity": {
    "value": <NUMERIC_VALUE>,
    "unit": "<DISPLAY_UNIT>",
    "system": "[url-4]",
    "code": "<UCUM_CODE>"
  }
}
```

## FHIR Bundle Template

For multiple observations:

```json
{
  "resourceType": "Bundle",
  "id": "<uuid>",
  "type": "collection",
  "timestamp": "<ISO_TIMESTAMP>",
  "entry": [
    {
      "fullUrl": "urn:uuid:<observation-uuid>",
      "resource": { /* Observation */ }
    }
  ]
}
```

## Heart Rate Observation Example

```json
{
  "resourceType": "Observation",
  "id": "hr-20251129-143000",
  "status": "final",
  "category": [{
    "coding": [{
      "system": "[url-2]",
      "code": "vital-signs",
      "display": "Vital Signs"
    }]
  }],
  "code": {
    "coding": [{
      "system": "[url-3]",
      "code": "8867-4",
      "display": "Heart rate"
    }],
    "text": "Heart Rate"
  },
  "subject": {
    "reference": "Patient/self"
  },
  "effectiveDateTime": "2025-11-29T14:30:00+01:00",
  "valueQuantity": {
    "value": 72,
    "unit": "beats/minute",
    "system": "[url-4]",
    "code": "/min"
  }
}
```

## Sleep Duration Observation Example

```json
{
  "resourceType": "Observation",
  "id": "sleep-20251129",
  "status": "final",
  "category": [{
    "coding": [{
      "system": "[url-2]",
      "code": "sleep-wake",
      "display": "Sleep"
    }]
  }],
  "code": {
    "coding": [{
      "system": "[url-3]",
      "code": "93832-4",
      "display": "Sleep duration"
    }],
    "text": "Sleep Duration"
  },
  "effectivePeriod": {
    "start": "2025-11-28T23:30:00+01:00",
    "end": "2025-11-29T07:15:00+01:00"
  },
  "valueQuantity": {
    "value": 7.75,
    "unit": "hours",
    "system": "[url-4]",
    "code": "h"
  },
  "component": [
    {
      "code": {
        "coding": [{
          "system": "[url-3]",
          "code": "93831-0",
          "display": "Deep sleep duration"
        }]
      },
      "valueQuantity": {
        "value": 1.5,
        "unit": "hours",
        "system": "[url-4]",
        "code": "h"
      }
    },
    {
      "code": {
        "coding": [{
          "system": "[url-3]",
          "code": "93830-2",
          "display": "REM sleep duration"
        }]
      },
      "valueQuantity": {
        "value": 2.0,
        "unit": "hours",
        "system": "[url-4]",
        "code": "h"
      }
    }
  ]
}
```

## Activity Bundle Example

```json
{
  "resourceType": "Bundle",
  "id": "daily-activity-20251129",
  "type": "collection",
  "timestamp": "2025-11-29T23:59:59Z",
  "entry": [
    {
      "fullUrl": "urn:uuid:steps-20251129",
      "resource": {
        "resourceType": "Observation",
        "id": "steps-20251129",
        "status": "final",
        "category": [{
          "coding": [{
            "system": "[url-2]",
            "code": "activity",
            "display": "Activity"
          }]
        }],
        "code": {
          "coding": [{
            "system": "[url-3]",
            "code": "55423-8",
            "display": "Number of steps"
          }]
        },
        "effectiveDateTime": "2025-11-29",
        "valueQuantity": {
          "value": 8542,
          "unit": "steps",
          "system": "[url-4]",
          "code": "{steps}"
        }
      }
    },
    {
      "fullUrl": "urn:uuid:calories-20251129",
      "resource": {
        "resourceType": "Observation",
        "id": "calories-20251129",
        "status": "final",
        "category": [{
          "coding": [{
            "system": "[url-2]",
            "code": "activity",
            "display": "Activity"
          }]
        }],
        "code": {
          "coding": [{
            "system": "[url-3]",
            "code": "41981-2",
            "display": "Calories burned"
          }]
        },
        "effectiveDateTime": "2025-11-29",
        "valueQuantity": {
          "value": 2150,
          "unit": "kcal",
          "system": "[url-4]",
          "code": "kcal"
        }
      }
    }
  ]
}
```

## References

- [FHIR R4 Vital Signs Profile]([url-5])
- [FHIR R4 Heart Rate Profile]([url-6])
- [LOINC Codes]([url-7])
- [UCUM Units]([url-8])
