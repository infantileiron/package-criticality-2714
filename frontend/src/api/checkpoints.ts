import {request} from './client';import type {Checkpoint} from '../types/domain';
export const list=(scenarioId?:string)=>request<Checkpoint[]>('/checkpoints'+(scenarioId?'?scenario_id='+encodeURIComponent(scenarioId):''));
export const detail=(id:string)=>request<Checkpoint>('/checkpoints/'+encodeURIComponent(id));
export const create=(data:unknown)=>request<Checkpoint>('/checkpoints',data);
