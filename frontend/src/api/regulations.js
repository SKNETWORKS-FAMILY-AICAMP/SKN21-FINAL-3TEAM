import client from './client'

export const listRegulations = () => client.get('/regulations')
