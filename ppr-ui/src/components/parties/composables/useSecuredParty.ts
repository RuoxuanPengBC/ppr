import { reactive, toRefs, computed } from '@vue/composition-api'
import { PartyIF, AddressIF } from '@/interfaces' // eslint-disable-line no-unused-vars
import { useGetters, useActions } from 'vuex-composition-helpers'
import { PartyAddressSchema } from '@/schemas'
import { APIRegistrationTypes } from '@/enums'

const initPerson = { first: '', middle: '', last: '' }
const initAddress = {
  street: '',
  streetAdditional: '',
  city: '',
  region: '',
  country: '',
  postalCode: '',
  deliveryInstructions: ''
}

export const useSecuredParty = (props, context) => {
  const { setAddSecuredPartiesAndDebtors } = useActions<any>([
    'setAddSecuredPartiesAndDebtors'
  ])
  const { getAddSecuredPartiesAndDebtors } = useGetters<any>([
    'getAddSecuredPartiesAndDebtors'
  ])
  const localState = reactive({
    currentSecuredParty: {
      businessName: '',
      personName: initPerson,
      emailAddress: '',
      address: initAddress
    } as PartyIF,
    currentIsBusiness: null
  })

  const getSecuredParty = () => {
    const securedParties: PartyIF[] =
      getAddSecuredPartiesAndDebtors.value.securedParties
    if (props.activeIndex >= 0) {
      localState.currentSecuredParty = securedParties[props.activeIndex]
      localState.currentIsBusiness = false
      if (localState.currentSecuredParty.businessName) {
        localState.currentIsBusiness = true
      }
    } else {
      const blankSecuredParty = {
        businessName: '',
        personName: Object.assign({}, initPerson),
        birthDate: '',
        emailAddress: '',
        address: Object.assign({}, initAddress)
      }
      localState.currentSecuredParty = blankSecuredParty
    }
  }

  const addressSchema = PartyAddressSchema

  const resetFormAndData = (emitEvent: boolean): void => {
    if (emitEvent) {
      context.emit('resetEvent')
    }
  }
  const removeSecuredParty = (): void => {
    context.emit('removeSecuredParty', props.activeIndex)
    resetFormAndData(true)
  }

  const addEditSecuredParty = async () => {
    let parties = getAddSecuredPartiesAndDebtors.value // eslint-disable-line
    let newList: PartyIF[] = parties.securedParties // eslint-disable-line
    // New secured party
    if (props.activeIndex === -1) {
      newList.push(localState.currentSecuredParty)
    } else {
      // Edit vehicle
      newList.splice(props.activeIndex, 1, localState.currentSecuredParty)
    }
    parties.securedParties = newList
    setAddSecuredPartiesAndDebtors(parties)
    context.emit('resetEvent')
  }

  const addSecuredParty = (newParty: PartyIF) => {
    let parties = getAddSecuredPartiesAndDebtors.value // eslint-disable-line
    let newList: PartyIF[] = parties.securedParties // eslint-disable-line
    newList.push(newParty)
    parties.securedParties = newList
    setAddSecuredPartiesAndDebtors(parties)
  }

  /**
   * Handles update events from address sub-components.
   */
  const updateAddress = (newAddress: AddressIF): void => {
    localState.currentSecuredParty.address = newAddress
  }

  const isSecuredPartyRestrictedList = (regType: string): boolean => {
    const restrictedList = [
      APIRegistrationTypes.LIEN_UNPAID_WAGES,
      APIRegistrationTypes.PROCEEDS_CRIME_NOTICE,
      APIRegistrationTypes.HERITAGE_CONSERVATION_NOTICE,
      APIRegistrationTypes.INSURANCE_PREMIUM_TAX,
      APIRegistrationTypes.PETROLEUM_NATURAL_GAS_TAX,
      APIRegistrationTypes.FOREST,
      APIRegistrationTypes.LOGGING_TAX,
      APIRegistrationTypes.CARBON_TAX,
      APIRegistrationTypes.PROVINCIAL_SALES_TAX,
      APIRegistrationTypes.RURAL_PROPERTY_TAX,
      APIRegistrationTypes.INCOME_TAX,
      APIRegistrationTypes.MOTOR_FUEL_TAX,
      APIRegistrationTypes.EXCISE_TAX,
      APIRegistrationTypes.MAINTENANCE_LIEN,
      APIRegistrationTypes.MANUFACTURED_HOME_NOTICE,
      APIRegistrationTypes.OTHER,
      APIRegistrationTypes.MINERAL_LAND_TAX,
      APIRegistrationTypes.PROPERTY_TRANSFER_TAX,
      APIRegistrationTypes.SCHOOL_ACT
    ]
    // @ts-ignore - it doesn't like the string comparison for some reason
    if (restrictedList.includes(regType)) {
      return true
    }
    return false
  }

  return {
    getSecuredParty,
    addEditSecuredParty,
    resetFormAndData,
    removeSecuredParty,
    addressSchema,
    updateAddress,
    addSecuredParty,
    isSecuredPartyRestrictedList,
    ...toRefs(localState)
  }
}
