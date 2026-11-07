/* Mileage validation: digits only, maximum six digits / 999999. */
document.addEventListener('DOMContentLoaded',function(){
 const mileageField=document.querySelector('#listingForm input[name="mileage"]');
 if(!mileageField)return;
 mileageField.addEventListener('input',function(){
  const digits=this.value.replace(/\D/g,'').slice(0,6);
  this.value=digits;
 });
 mileageField.addEventListener('blur',function(){
  if(this.value && Number(this.value)>999999)this.value='999999';
 });
});
