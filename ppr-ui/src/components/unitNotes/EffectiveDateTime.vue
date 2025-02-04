<template>
  <div id="effective-date-time-container">
    <h2>
      {{ `${sectionNumber ? sectionNumber + '.' : ''} ${content.title}`}}
    </h2>
    <p class="mt-2">{{ content.description }}</p>
    <v-card
      id="effective-date-time-card"
      class="mt-8 px-7 pt-10 pb-3"
      :class="{ 'border-error-left': showBorderError }"
      flat
    >
      <v-row no-gutters>
        <v-col cols="12" sm="3">
          <label class="generic-label" :class="{ 'error-text': showBorderError }">
            {{ content.sideLabel }}
          </label>
        </v-col>
        <v-col cols="12" sm="9" class="px-1">
          <v-radio-group v-model="effectiveDateType" column class="pt-0 mt-0">
            <v-radio
              :value="EffectiveDateTypes.IMMEDIATE"
              label="Immediate (date and time of registration)"
              data-test-id="immediate-date-radio"
            />
            <v-radio
              :value="EffectiveDateTypes.PAST"
              label="Date and time in the past"
              data-test-id="past-date-radio"
            />
          </v-radio-group>
          <v-form ref="effectiveDateTimeForm" class="date-time-selectors" v-model="isEffectiveDateTimeFormValid">
            <SharedDatePicker
              id="effective-date-picker"
              ref="effectiveDatePicker"
              title="Date"
              :initialValue="selectedPastDate"
              :disablePicker="isImmediateDateSelected"
              :inputRules="required('This field is required')"
              :maxDate="maxDate"
              @emitDate="selectedPastDate = $event"
              @emitCancel="selectedPastDate = ''"
              @emitClear="selectedPastDate = ''"
            />

            <div class="time-picker" data-test-id="time-picker-fields">
              <v-select
                id="hour-selector"
                ref="hourSelector"
                v-model="selectHour"
                filled
                class="mr-1"
                label="Hour"
                :items="hours"
                :rules="required('This field is required')"
                :disabled="isImmediateDateSelected"
              />
              <span class="time-separator pt-4" :class="{ disabled: isImmediateDateSelected }"> : </span>

              <v-select
                id="minute-selector"
                ref="minuteSelector"
                v-model="selectMinute"
                filled
                class="mr-1"
                label="Minute"
                :items="minutes"
                :rules="required('This field is required')"
                :disabled="isImmediateDateSelected"
              />

              <v-select
                id="period-selector"
                ref="periodSelector"
                v-model="selectPeriod"
                filled
                class="mr-1 period-selector"
                :items="[PeriodTypes.AM, PeriodTypes.PM]"
                :disabled="isImmediateDateSelected"
              />

              <span class="timezone-label pt-4" :class="{ disabled: isImmediateDateSelected }"> Pacific time </span>
            </div>
          </v-form>

          <p
            v-if="!isImmediateDateSelected && selectedPastDate && isTimeSelected"
            class="ml-8 mb-6"
            data-test-id="date-summary-label"
          >
            {{ content.dateSummaryLabel }} <br />
            <b>
              {{ pacificDate(effectiveDate, true) }}
            </b>
          </p>
        </v-col>
      </v-row>
    </v-card>
  </div>
</template>

<script lang="ts">
import { computed, defineComponent, reactive, ref, toRefs, watch } from 'vue-demi'
import { EffectiveDateTypes, PeriodTypes } from '@/enums/'
import { createDateFromPacificTime, localTodayDate, pacificDate } from '@/utils'
import { ContentIF, FormIF } from '@/interfaces'
import { useInputRules } from '@/composables'
import SharedDatePicker from '@/components/common/SharedDatePicker.vue'

export default defineComponent({
  name: 'EffectiveDateTime',
  components: {
    SharedDatePicker
  },
  props: {
    validate: {
      type: Boolean,
      default: false
    },
    sectionNumber: {
      type: Number,
      required: false
    },
    content: {
      type: Object as () => ContentIF,
      default: () => {}
    }
  },
  emits: ['isValid', 'setStoreProperty'],
  setup (props, { emit }) {
    const { required } = useInputRules()

    const effectiveDatePicker = ref(null) as FormIF
    const effectiveDateTimeForm = ref(null) as FormIF

    const date = new Date()

    const localState = reactive({
      isEffectiveDateTimeFormValid: true,
      selectHour: null,
      selectMinute: null,
      selectPeriod: PeriodTypes.AM,
      selectedPastDate: '', // date selected from the Date Picker

      effectiveDateType: EffectiveDateTypes.IMMEDIATE,
      effectiveDate: '',

      hours: [...Array(12).keys()].map(num => (num + 1).toString()),
      minutes: [...Array(60).keys()].map(num => num.toString().padStart(2, '0')),
      maxDate: computed((): string => localTodayDate(new Date(date.setDate(date.getDate() - 1)))),
      isImmediateDateSelected: computed((): boolean => localState.effectiveDateType === EffectiveDateTypes.IMMEDIATE),
      isTimeSelected: computed((): boolean => !!localState.selectHour && !!localState.selectMinute),
      isEffectiveDateTimeValid: computed((): boolean =>
        localState.isImmediateDateSelected ||
        (!localState.isImmediateDateSelected && !!localState.selectedPastDate &&
          localState.isTimeSelected)
      ),
      showBorderError: computed((): boolean => {
        return props.validate &&
        !localState.isImmediateDateSelected &&
        !(localState.isEffectiveDateTimeFormValid && localState.selectedPastDate !== '')
      })

    })

    const buildFullDate = (): Date => {
      const YearMonthDay = localState.selectedPastDate.split('-')
      const year = parseInt(YearMonthDay[0])
      const month = parseInt(YearMonthDay[1]) - 1
      const day = parseInt(YearMonthDay[2])
      let hours = parseInt(localState.selectHour)
      const minutes = parseInt(localState.selectMinute)

      // convert 12 am -> 0
      if (localState.selectPeriod === PeriodTypes.AM && hours === 12) {
        hours = hours - 12
      }
      // convert 1-11 pm -> 13-23
      if (localState.selectPeriod === PeriodTypes.PM && hours < 12) {
        hours = hours + 12
      }

      return createDateFromPacificTime(year, month, day, hours, minutes)
    }

    watch(() => props.validate, async (val) => {
      if (val && !localState.isImmediateDateSelected) {
        effectiveDatePicker.value?.validate()
        effectiveDateTimeForm.value?.validate()
      }
    })

    watch(
      () => [localState.effectiveDateType],
      () => {
        if (localState.isImmediateDateSelected) {
          // Let the API set the effective date and time
          localState.effectiveDate = ''
        } else if (props.validate) {
          effectiveDatePicker.value?.validate()
          effectiveDateTimeForm.value.validate()
        } else if (localState.isTimeSelected && !!localState.selectedPastDate) {
          // past date radio selected and all time dropdowns are selected
          localState.effectiveDate = buildFullDate().toISOString()
        }
      }
    )

    watch(
      () => [localState.selectedPastDate, localState.selectHour, localState.selectMinute, localState.selectPeriod],
      () => {
        if (localState.isTimeSelected && !!localState.selectedPastDate) {
          localState.effectiveDate = buildFullDate().toISOString()
        }
      }
    )

    watch(
      () => localState.effectiveDate,
      val => {
        emit('setStoreProperty', val)
      }
    )

    watch(() => localState.isEffectiveDateTimeValid, (val: boolean) => {
      emit('isValid', val)
    }, { immediate: true })

    return {
      required,
      effectiveDatePicker,
      effectiveDateTimeForm,
      EffectiveDateTypes,
      PeriodTypes,
      pacificDate,
      ...toRefs(localState)
    }
  }
})
</script>

<style lang="scss" scoped>
@import '@/assets/styles/theme.scss';

.time-picker {
  display: flex;
  gap: 5px;
  justify-content: space-between;
  align-content: center;
  max-width: 600px;
  .v-select {
    max-width: 148px;
  }

  .time-separator {
    margin-right: 2px;
  }

  .period-selector::v-deep .v-input__slot{
    height: 58px;
  }

  .timezone-label {
    white-space: nowrap;
  }
}

.v-radio {
  padding-bottom: 0.5rem;
}

.date-time-selectors {
  margin-left: 2rem;
}

.disabled {
  color: $gray6;
}

.v-icon.v-icon.v-icon--disabled {
  color: $app-blue !important;
}
.v-input--is-disabled {
  opacity: 0.4;
}
</style>
