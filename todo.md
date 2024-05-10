### Features
#### My Use-case
* Add more data to jobs table
* Make navigation of jobs table faster
  * Expand subtree button
* Revisit: Handle graph scaling to viewport size
* Pipepline depth limit selection
* move settings to modal
* Add more info to job panel
  * timestamp
  * sub jobs
  * history
  * downstream
* Datetime filter on table
* renable textual output
* configurable server port
* do more caching & pre-loading to speed up dashboard
  * especially around switching views, it's very slow right now
* dynamic generate subtree here options
  * will recurse jenkins from the selected job and show the new dynamic graph
  * would allow for more dynamic drilldown, especially from a customer pipeline-config that doesn't have every job
* make the subway map more compact, we waste a bunch of space
* Idea: if subgraph has a clear in-out with a bunch of complexity in the middle, collapse it
#### Generalizing (other use-cases)
* Integration with other workflow engines
* Specify which job parameters to track (rather than fixed "SERIAL")
* Jenkins folder support

### Performance
* speed up `generate_plot_figure`
  * currently taking 200-300 ms for ibm_oracle network
  * layout:updatemenus is taking a good chunk of that time
  * everything around annotations is adding a good chunk of time
    * get_node_labels 20%, fig.update_layout 52%

### Maintainability
* take another look at improving the custom-callback syntax for components. @decorator somehow?
* Take another look at top level callbacks and dependency on id string
* set global prevent_initial_callback and adjust individual callbacks
* refactor data importer to make it easier to add other sources of data
* testing
  * callback testing using dash framework
  * unit testing around core logic
* add more logging?
  * TODO
* improve error handling on data import
  * early detection if job doesn't exist on server (rather than retrying till timeout)
* tox (test, lint, black)
* PyPi package
* Snap package


### Bugs
* fix that stupid Label On/Off button in dark mode
  * problem in Plotly, 
  * might need to create a floating button to replace it?
  * or, fix in plotly upstream


### Documentation
* Write more thorough docs on job config files
* docstrings on the key classes / functions
* Create an online demo
  * JJB -> Jenkikns -> PD Job Config -> PD Dash
* Create an offline demo
  * Use cache data from oneline demo
  * Cache -> PD Job Config -> PD Dash