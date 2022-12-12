* Use `recurse` option in YAML to determine if to recurse jobs or not.
  * Currently, will recurse everything if `recurse` command is used
  * Need to refactor how we're determining what job_data to collect, right now we're collecting everything
* Add more data to jobs table
* Make navigation of jobs table faster
  * Expand subtree button
* Revisit: Handle graph scaling to viewport size
* Pipepline depth limit selection
* move settings to modal
* take another look at improving the custom-callback syntax for components. @decorator somehow?
* Take another look at top level callbacks and dependency on id string
* Add more info to job panel
  * timestamp
  * sub jobs
  * history
  * downstream
* Datetime filter on table
* set global prevent_initial_callback and adjust individual callbacks
* refactor data importer to make it easier to add other sources of data
* testing
  * callback testing using dash framework
  * unit testing around core logic
* fix that stupid Label On/Off button in dark mode
  * problem in Plotly, 
  * might need to create a floating button to replace it?
  * or, fix in plotly upstream
* Write more thorough docks on job config files
* renable textual output
* add proper logging
  * especially around callbacks
* actual error handling on data import
* actual error handling when parsing YAML