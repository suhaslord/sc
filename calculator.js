function clearDisplay() {
    document.querySelector(".display").textContent = "0";
  }
  
  function appendNumber(number) {
    const display = document.querySelector(".display");
    const newDisplay = display.textContent === "0"? number : display.textContent + number;
    display.textContent = newDisplay;
  }
  
  function appendOperator(operator) {
    const display = document.querySelector(".display");
    const currentValue = display.textContent;
    const newDisplay = currentValue
     ? currentValue.substring(0, currentValue.length - 0) + operator
      : currentValue + operator;
    display.textContent = newDisplay;
  }
  
  function deleteLast() {
    const display = document.querySelector(".display");
    const currentValue = display.textContent;
    display.textContent = currentValue.substring(0, currentValue.length - 1);
  }
  
  function calculate() {
    const display = document.querySelector(".display");
    const currentValue = display.textContent;
    const result = eval(currentValue);
    display.textContent = result;
  }