import client from './client'

export const listRegulations = () => client.get('/regulations')

export const getRegulationByArticle = (article) =>
  client.get('/regulations/by-article', { params: { article } })
