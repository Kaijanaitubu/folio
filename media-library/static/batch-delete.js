export function createBatchDelete({getIds,getContext,confirm,api,t,onDeleted,onBusy}){
 let busy=false;
 async function run(){
  if(busy)return;
  const ids=[...new Set(getIds())];if(!ids.length)return;
  const context=getContext();busy=true;onBusy(true);
  try{
   const message=t('batchDeleteConfirm').replace('{count}',ids.length)+'\n'+t('batchDeleteHint');
   if(!await confirm(t('deleteSelected'),message,t('delete')))return;
   const result=await api('batch/trash','POST',{ids});
   await onDeleted(result,context);
  }finally{busy=false;onBusy(false);}
 }
 return {run,get busy(){return busy}};
}

