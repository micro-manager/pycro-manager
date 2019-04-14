/*
 * To change this license header, choose License Headers in Project Properties.
 * To change this template file, choose Tools | Templates
 * and open the template in the editor.
 */
package main.java.org.micromanager.plugins.magellan.imagedisplay;

import main.java.org.micromanager.plugins.magellan.acq.Acquisition;
import main.java.org.micromanager.plugins.magellan.acq.ExploreAcquisition;
import main.java.org.micromanager.plugins.magellan.gui.SimpleChannelTableModel;
import com.google.common.eventbus.EventBus;
import com.google.common.eventbus.Subscribe;
import java.awt.CardLayout;
import java.awt.Color;
import java.awt.Panel;
import java.awt.event.MouseEvent;
import java.awt.event.MouseMotionAdapter;
import javax.swing.BorderFactory;
import javax.swing.DefaultCellEditor;
import javax.swing.JLabel;
import javax.swing.JPanel;
import javax.swing.JTextField;
import javax.swing.Popup;
import javax.swing.PopupFactory;
import javax.swing.SwingConstants;
import javax.swing.event.ListSelectionEvent;
import javax.swing.event.ListSelectionListener;
import javax.swing.table.DefaultTableCellRenderer;
import javax.swing.table.DefaultTableModel;
import main.java.org.micromanager.plugins.magellan.json.JSONObject;
import main.java.org.micromanager.plugins.magellan.main.Magellan;
import main.java.org.micromanager.plugins.magellan.misc.ExactlyOneRowSelectionModel;
import main.java.org.micromanager.plugins.magellan.misc.MD;
import main.java.org.micromanager.plugins.magellan.surfacesandregions.MultiPosGrid;
import main.java.org.micromanager.plugins.magellan.surfacesandregions.SurfaceGridManager;
import main.java.org.micromanager.plugins.magellan.surfacesandregions.SurfaceInterpolator;
import main.java.org.micromanager.plugins.magellan.surfacesandregions.XYFootprint;

/**
 *
 * @author henrypinkard
 */
public class DisplayWindowControls extends Panel {

   private static final Color LIGHT_BLUE = new Color(200, 200, 255);

   private EventBus bus_;
   private DisplayPlus display_;
   private SurfaceGridManager manager_ = SurfaceGridManager.getInstance();
   private Acquisition acq_;
   private Popup instructionsPopup_;
   private volatile int selectedSurfaceGridIndex_ = -1;

   /**
    * Creates new form DisplayWindowControls
    */
   public DisplayWindowControls(DisplayPlus disp, EventBus bus, Acquisition acq) {
      bus_ = bus;
      display_ = disp;
      disp.registerControls(this);
      bus_.register(this);
      acq_ = acq;
      initComponents();

      if (acq_ instanceof ExploreAcquisition) {
         //left justified editor
         JTextField tf = new JTextField();
         tf.setHorizontalAlignment(SwingConstants.LEFT);
         DefaultCellEditor ed = new DefaultCellEditor(tf);
         channelsTable_.getColumnModel().getColumn(2).setCellEditor(ed);
         //and renderer
         DefaultTableCellRenderer renderer = new DefaultTableCellRenderer();
         renderer.setHorizontalAlignment(SwingConstants.LEFT); // left justify
         channelsTable_.getColumnModel().getColumn(2).setCellRenderer(renderer);
         //start in explore
         tabbedPane_.setSelectedIndex(1);
      } else {
         tabbedPane_.remove(1); //remove explore tab
         acquireAtCurrentButton_.setVisible(false);
      }

      //exactly one surface or grid selected at all times
      surfaceGridTable_.setSelectionModel(new ExactlyOneRowSelectionModel());
      surfaceGridTable_.getSelectionModel().addListSelectionListener(new ListSelectionListener() {
         @Override
         public void valueChanged(ListSelectionEvent e) {
            if (e.getValueIsAdjusting()) {
               return;
               //action occurs second time this method is called, after the table gains focus
            }
            selectedSurfaceGridIndex_ = surfaceGridTable_.getSelectedRow();
            //if last acq in list is removed, update the selected index
            if (selectedSurfaceGridIndex_ == surfaceGridTable_.getModel().getRowCount()) {
               surfaceGridTable_.getSelectionModel().setSelectionInterval(selectedSurfaceGridIndex_ - 1, selectedSurfaceGridIndex_ - 1);
            }
            XYFootprint current = getCurrentSurfaceOrGrid();
            if (current != null) {
               CardLayout card1 = (CardLayout) surfaceGridSpecificControlsPanel_.getLayout();
               card1.show(surfaceGridSpecificControlsPanel_, current instanceof SurfaceInterpolator ? "surface" : "grid");
            }
            display_.drawOverlay();
         }
      });
      //Table column widths
      surfaceGridTable_.getColumnModel().getColumn(0).setMaxWidth(40); //show column
   }

   XYFootprint getCurrentSurfaceOrGrid() {
      if (selectedSurfaceGridIndex_ == -1) {
         return null;
      }
      return SurfaceGridManager.getInstance().getSurfaceOrGrid(selectedSurfaceGridIndex_);
   }

   public void hideInstructionsPopup() {
      if (instructionsPopup_ != null) {
         instructionsPopup_.hide();
         instructionsPopup_ = null;
         DisplayWindowControls.this.repaint();
      }
   }

   private void setupPopupHints() {
      //make custom instruction popups disappear
      tabbedPane_.addMouseMotionListener(new MouseMotionAdapter() {
         @Override
         public void mouseMoved(MouseEvent e) {
            hideInstructionsPopup();
         }
      });

   }

   public void showStartupHints() {
      if (acq_ instanceof ExploreAcquisition) {
         showInstructionLabel("<html>Left click or click and drag to select tiles <br>"
                 + "Left click again to confirm <br>Right click and drag to pan<br>+/- keys or mouse wheel to zoom in/out</html>");
      } else {
         showInstructionLabel("<html>Right click and drag to pan<br>+/- keys or mouse wheel to zoom in/out</html>");
      }
      setupPopupHints();
   }

   @Subscribe
   public void onNewImageEvent(NewImageEvent e) {
      //once there's an image, surfaces and grids are game
      tabbedPane_.setEnabledAt(0, true);
   }

   @Subscribe
   public void onSetImageEvent(ScrollerPanel.SetImageEvent event) {
      if (display_.isClosing()) {
         return;
      }
      JSONObject tags = display_.getCurrentMetadata();
      if (tags == null) {
         return;
      }

      //update status panel
//      long sizeBytes = acq_.getStorage().getDataSetSize();
//      if (sizeBytes < 1024) {
//         datasetSizeLabel_.setText(sizeBytes + "  Bytes");
//      } else if (sizeBytes < 1024 * 1024) {
//         datasetSizeLabel_.setText(sizeBytes / 1024 + "  KB");
//      } else if (sizeBytes < 1024l * 1024 * 1024) {
//         datasetSizeLabel_.setText(sizeBytes / 1024 / 1024 + "  MB");
//      } else if (sizeBytes < 1024l * 1024 * 1024 * 1024) {
//         datasetSizeLabel_.setText(sizeBytes / 1024 / 1024 / 1024 + "  GB");
//      } else {
//         datasetSizeLabel_.setText(sizeBytes / 1024 / 1024 / 1024 / 1024 + "  TB");
//      }
      long elapsed = MD.getElapsedTimeMs(tags);
      long days = elapsed / (60 * 60 * 24 * 1000), hours = elapsed / 60 / 60 / 1000, minutes = elapsed / 60 / 1000, seconds = elapsed / 1000;

      hours = hours % 24;
      minutes = minutes % 60;
      seconds = seconds % 60;
      String h = ("0" + hours).substring(("0" + hours).length() - 2);
      String m = ("0" + (minutes)).substring(("0" + minutes).length() - 2);
      String s = ("0" + (seconds)).substring(("0" + seconds).length() - 2);
      String label = days + ":" + h + ":" + m + ":" + s + " (D:H:M:S)";

      elapsedTimeLabel_.setText(label);
      zPosLabel_.setText("Display Z position " + MD.getZPositionUm(tags) + "um");
   }

   public void prepareForClose() {
      bus_.unregister(this);
      ((DisplayWindowSurfaceGridTableModel) surfaceGridTable_.getModel()).shutdown();
      if (acq_ instanceof ExploreAcquisition) {
         ((SimpleChannelTableModel) channelsTable_.getModel()).shutdown();
      }
   }

   private MultiPosGrid createNewGrid() {
      int imageWidth = display_.getImagePlus().getWidth();
      int imageHeight = display_.getImagePlus().getHeight();
      return new MultiPosGrid(manager_, Magellan.getCore().getXYStageDevice(),
              (Integer) gridRowsSpinner_.getValue(), (Integer) gridColsSpinner_.getValue(),
              display_.stageCoordFromImageCoords(imageWidth / 2, imageHeight / 2));
   }

   private void showInstructionLabel(String text) {
      if (!tabbedPane_.getSelectedComponent().isShowing()) {
         return;
      }

      if (instructionsPopup_ != null) {
         instructionsPopup_.hide();
      }
      PopupFactory popupFactory = PopupFactory.getSharedInstance();
      int x = tabbedPane_.getSelectedComponent().getLocationOnScreen().x;
      int y = tabbedPane_.getSelectedComponent().getLocationOnScreen().y;

      JPanel background = new JPanel();
      background.setBorder(BorderFactory.createLineBorder(Color.black));
      background.setBackground(LIGHT_BLUE); //light green
      JLabel message = new JLabel(text);
      message.setForeground(Color.black);
      background.add(message);
      x += tabbedPane_.getSelectedComponent().getWidth() / 2 - background.getPreferredSize().width / 2;
      y += tabbedPane_.getSelectedComponent().getHeight() / 2 - background.getPreferredSize().height / 2;
      instructionsPopup_ = popupFactory.getPopup(tabbedPane_.getSelectedComponent(), background, x, y);
      instructionsPopup_.show();
   }

   /**
    * This method is called from within the constructor to initialize the form.
    * WARNING: Do NOT modify this code. The content of this method is always
    * regenerated by the Form Editor.
    */
   @SuppressWarnings("unchecked")
   // <editor-fold defaultstate="collapsed" desc="Generated Code">//GEN-BEGIN:initComponents
   private void initComponents() {

      tabbedPane_ = new javax.swing.JTabbedPane();
      surfaceGridPanel_ = new javax.swing.JPanel();
      jScrollPane2 = new javax.swing.JScrollPane();
      surfaceGridTable_ = new javax.swing.JTable();
      surfaceGridSpecificControlsPanel_ = new javax.swing.JPanel();
      gridControlPanel_ = new javax.swing.JPanel();
      gridRowsLabel_ = new javax.swing.JLabel();
      gridRowsSpinner_ = new javax.swing.JSpinner();
      gridColsLabel_ = new javax.swing.JLabel();
      gridColsSpinner_ = new javax.swing.JSpinner();
      jLabel1 = new javax.swing.JLabel();
      surfaceControlPanel_ = new javax.swing.JPanel();
      showStagePositionsCheckBox_ = new javax.swing.JCheckBox();
      showInterpCheckBox_ = new javax.swing.JCheckBox();
      jLabel2 = new javax.swing.JLabel();
      addSurfaceGridButtonPanel_ = new javax.swing.JPanel();
      newGridButton_ = new javax.swing.JButton();
      newSurfaceButton_ = new javax.swing.JButton();
      explorePanel_ = new javax.swing.JPanel();
      jScrollPane1 = new javax.swing.JScrollPane();
      channelsTable_ = new javax.swing.JTable();
      showInFolderButton_ = new javax.swing.JButton();
      abortButton_ = new javax.swing.JButton();
      pauseButton_ = new javax.swing.JButton();
      fpsLabel_ = new javax.swing.JLabel();
      animationFPSSpinner_ = new javax.swing.JSpinner();
      showNewImagesCheckBox_ = new javax.swing.JCheckBox();
      elapsedTimeLabel_ = new javax.swing.JLabel();
      zPosLabel_ = new javax.swing.JLabel();
      acquireAtCurrentButton_ = new javax.swing.JButton();

      tabbedPane_.setToolTipText("");
      tabbedPane_.addChangeListener(new javax.swing.event.ChangeListener() {
         public void stateChanged(javax.swing.event.ChangeEvent evt) {
            tabbedPane_StateChanged(evt);
         }
      });

      surfaceGridTable_.setModel(new DisplayWindowSurfaceGridTableModel()
      );
      surfaceGridTable_.setSelectionMode(javax.swing.ListSelectionModel.SINGLE_SELECTION);
      jScrollPane2.setViewportView(surfaceGridTable_);

      surfaceGridSpecificControlsPanel_.setLayout(new java.awt.CardLayout());

      gridRowsLabel_.setText("Rows:");

      gridRowsSpinner_.setModel(new javax.swing.SpinnerNumberModel(1, 1, null, 1));
      gridRowsSpinner_.addChangeListener(new javax.swing.event.ChangeListener() {
         public void stateChanged(javax.swing.event.ChangeEvent evt) {
            gridRowsSpinner_StateChanged(evt);
         }
      });

      gridColsLabel_.setText("Columns:");

      gridColsSpinner_.setModel(new javax.swing.SpinnerNumberModel(1, 1, null, 1));
      gridColsSpinner_.addChangeListener(new javax.swing.event.ChangeListener() {
         public void stateChanged(javax.swing.event.ChangeEvent evt) {
            gridColsSpinner_StateChanged(evt);
         }
      });

      jLabel1.setText("Current Grid: ");

      javax.swing.GroupLayout gridControlPanel_Layout = new javax.swing.GroupLayout(gridControlPanel_);
      gridControlPanel_.setLayout(gridControlPanel_Layout);
      gridControlPanel_Layout.setHorizontalGroup(
         gridControlPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(javax.swing.GroupLayout.Alignment.TRAILING, gridControlPanel_Layout.createSequentialGroup()
            .addContainerGap()
            .addComponent(jLabel1)
            .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.UNRELATED)
            .addComponent(gridRowsLabel_)
            .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
            .addComponent(gridRowsSpinner_, javax.swing.GroupLayout.PREFERRED_SIZE, 56, javax.swing.GroupLayout.PREFERRED_SIZE)
            .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
            .addComponent(gridColsLabel_)
            .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
            .addComponent(gridColsSpinner_, javax.swing.GroupLayout.PREFERRED_SIZE, 54, javax.swing.GroupLayout.PREFERRED_SIZE)
            .addContainerGap(96, Short.MAX_VALUE))
      );
      gridControlPanel_Layout.setVerticalGroup(
         gridControlPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(gridControlPanel_Layout.createSequentialGroup()
            .addGroup(gridControlPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.BASELINE)
               .addComponent(gridRowsLabel_)
               .addComponent(gridRowsSpinner_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)
               .addComponent(gridColsLabel_)
               .addComponent(gridColsSpinner_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE)
               .addComponent(jLabel1))
            .addGap(0, 26, Short.MAX_VALUE))
      );

      surfaceGridSpecificControlsPanel_.add(gridControlPanel_, "grid");

      showStagePositionsCheckBox_.setSelected(true);
      showStagePositionsCheckBox_.setText("XY Footprint postions");
      showStagePositionsCheckBox_.addActionListener(new java.awt.event.ActionListener() {
         public void actionPerformed(java.awt.event.ActionEvent evt) {
            showStagePositionsCheckBox_ActionPerformed(evt);
         }
      });

      showInterpCheckBox_.setSelected(true);
      showInterpCheckBox_.setText("Interpolation");
      showInterpCheckBox_.addActionListener(new java.awt.event.ActionListener() {
         public void actionPerformed(java.awt.event.ActionEvent evt) {
            showInterpCheckBox_ActionPerformed(evt);
         }
      });

      jLabel2.setText("Show:");

      javax.swing.GroupLayout surfaceControlPanel_Layout = new javax.swing.GroupLayout(surfaceControlPanel_);
      surfaceControlPanel_.setLayout(surfaceControlPanel_Layout);
      surfaceControlPanel_Layout.setHorizontalGroup(
         surfaceControlPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(surfaceControlPanel_Layout.createSequentialGroup()
            .addComponent(jLabel2)
            .addGap(21, 21, 21)
            .addComponent(showInterpCheckBox_)
            .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
            .addComponent(showStagePositionsCheckBox_)
            .addContainerGap(78, Short.MAX_VALUE))
      );
      surfaceControlPanel_Layout.setVerticalGroup(
         surfaceControlPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(surfaceControlPanel_Layout.createSequentialGroup()
            .addGroup(surfaceControlPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.BASELINE)
               .addComponent(showStagePositionsCheckBox_)
               .addComponent(showInterpCheckBox_)
               .addComponent(jLabel2))
            .addContainerGap(29, Short.MAX_VALUE))
      );

      surfaceGridSpecificControlsPanel_.add(surfaceControlPanel_, "surface");

      newGridButton_.setText("New Grid");
      newGridButton_.addActionListener(new java.awt.event.ActionListener() {
         public void actionPerformed(java.awt.event.ActionEvent evt) {
            newGridButton_ActionPerformed(evt);
         }
      });

      newSurfaceButton_.setText("New Surface");
      newSurfaceButton_.addActionListener(new java.awt.event.ActionListener() {
         public void actionPerformed(java.awt.event.ActionEvent evt) {
            newSurfaceButton_ActionPerformed(evt);
         }
      });

      javax.swing.GroupLayout addSurfaceGridButtonPanel_Layout = new javax.swing.GroupLayout(addSurfaceGridButtonPanel_);
      addSurfaceGridButtonPanel_.setLayout(addSurfaceGridButtonPanel_Layout);
      addSurfaceGridButtonPanel_Layout.setHorizontalGroup(
         addSurfaceGridButtonPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(addSurfaceGridButtonPanel_Layout.createSequentialGroup()
            .addComponent(newGridButton_)
            .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
            .addComponent(newSurfaceButton_)
            .addContainerGap(javax.swing.GroupLayout.DEFAULT_SIZE, Short.MAX_VALUE))
      );
      addSurfaceGridButtonPanel_Layout.setVerticalGroup(
         addSurfaceGridButtonPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(addSurfaceGridButtonPanel_Layout.createSequentialGroup()
            .addGroup(addSurfaceGridButtonPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.BASELINE)
               .addComponent(newGridButton_)
               .addComponent(newSurfaceButton_))
            .addGap(0, 0, Short.MAX_VALUE))
      );

      javax.swing.GroupLayout surfaceGridPanel_Layout = new javax.swing.GroupLayout(surfaceGridPanel_);
      surfaceGridPanel_.setLayout(surfaceGridPanel_Layout);
      surfaceGridPanel_Layout.setHorizontalGroup(
         surfaceGridPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(surfaceGridPanel_Layout.createSequentialGroup()
            .addContainerGap()
            .addComponent(addSurfaceGridButtonPanel_, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, Short.MAX_VALUE)
            .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
            .addComponent(surfaceGridSpecificControlsPanel_, javax.swing.GroupLayout.PREFERRED_SIZE, 424, javax.swing.GroupLayout.PREFERRED_SIZE))
         .addComponent(jScrollPane2)
      );
      surfaceGridPanel_Layout.setVerticalGroup(
         surfaceGridPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(surfaceGridPanel_Layout.createSequentialGroup()
            .addComponent(jScrollPane2, javax.swing.GroupLayout.PREFERRED_SIZE, 95, javax.swing.GroupLayout.PREFERRED_SIZE)
            .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED, javax.swing.GroupLayout.DEFAULT_SIZE, Short.MAX_VALUE)
            .addGroup(surfaceGridPanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING, false)
               .addComponent(surfaceGridSpecificControlsPanel_, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, Short.MAX_VALUE)
               .addComponent(addSurfaceGridButtonPanel_, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, Short.MAX_VALUE))
            .addGap(135, 135, 135))
      );

      tabbedPane_.addTab("Surfaces and Grids", surfaceGridPanel_);

      explorePanel_.setToolTipText("<html>Left click or click and drag to select tiles <br>Left click again to confirm <br>Right click and drag to pan<br>+/- keys or mouse wheel to zoom in/out</html>");

      channelsTable_.setModel(acq_ != null ? new SimpleChannelTableModel(acq_.getChannels(),false) : new DefaultTableModel());
      jScrollPane1.setViewportView(channelsTable_);

      javax.swing.GroupLayout explorePanel_Layout = new javax.swing.GroupLayout(explorePanel_);
      explorePanel_.setLayout(explorePanel_Layout);
      explorePanel_Layout.setHorizontalGroup(
         explorePanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addComponent(jScrollPane1, javax.swing.GroupLayout.DEFAULT_SIZE, 670, Short.MAX_VALUE)
      );
      explorePanel_Layout.setVerticalGroup(
         explorePanel_Layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addComponent(jScrollPane1, javax.swing.GroupLayout.Alignment.TRAILING, javax.swing.GroupLayout.DEFAULT_SIZE, 141, Short.MAX_VALUE)
      );

      tabbedPane_.addTab("Explore", explorePanel_);

      showInFolderButton_.setIcon(new javax.swing.ImageIcon(getClass().getResource("/main/resources/org/micromanager/folder.png"))); // NOI18N
      showInFolderButton_.setToolTipText("Show in folder");
      showInFolderButton_.addActionListener(new java.awt.event.ActionListener() {
         public void actionPerformed(java.awt.event.ActionEvent evt) {
            showInFolderButton_ActionPerformed(evt);
         }
      });

      abortButton_.setIcon(new javax.swing.ImageIcon(getClass().getResource("/main/resources/org/micromanager/abort.png"))); // NOI18N
      abortButton_.setToolTipText("Abort acquisition");
      abortButton_.addActionListener(new java.awt.event.ActionListener() {
         public void actionPerformed(java.awt.event.ActionEvent evt) {
            abortButton_ActionPerformed(evt);
         }
      });

      pauseButton_.setIcon(new javax.swing.ImageIcon(getClass().getResource("/main/resources/org/micromanager/pause.png"))); // NOI18N
      pauseButton_.setToolTipText("Pause/resume acquisition");
      pauseButton_.addActionListener(new java.awt.event.ActionListener() {
         public void actionPerformed(java.awt.event.ActionEvent evt) {
            pauseButton_ActionPerformed(evt);
         }
      });

      fpsLabel_.setText("Animate FPS:");

      animationFPSSpinner_.setModel(new javax.swing.SpinnerNumberModel(7.0d, 1.0d, 1000.0d, 1.0d));
      animationFPSSpinner_.setToolTipText("Speed of the scrollbar animation button playback");
      animationFPSSpinner_.addChangeListener(new javax.swing.event.ChangeListener() {
         public void stateChanged(javax.swing.event.ChangeEvent evt) {
            animationFPSSpinner_StateChanged(evt);
         }
      });

      showNewImagesCheckBox_.setSelected(true);
      showNewImagesCheckBox_.setText("Move scrollbars on new image");
      showNewImagesCheckBox_.addActionListener(new java.awt.event.ActionListener() {
         public void actionPerformed(java.awt.event.ActionEvent evt) {
            showNewImagesCheckBox_ActionPerformed(evt);
         }
      });

      elapsedTimeLabel_.setText("Elapsed time: ");

      zPosLabel_.setText("Display Z position: ");

      acquireAtCurrentButton_.setText("Acquire here");
      acquireAtCurrentButton_.addActionListener(new java.awt.event.ActionListener() {
         public void actionPerformed(java.awt.event.ActionEvent evt) {
            acquireAtCurrentButton_ActionPerformed(evt);
         }
      });

      javax.swing.GroupLayout layout = new javax.swing.GroupLayout(this);
      this.setLayout(layout);
      layout.setHorizontalGroup(
         layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(layout.createSequentialGroup()
            .addGroup(layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
               .addGroup(layout.createSequentialGroup()
                  .addGap(0, 0, Short.MAX_VALUE)
                  .addComponent(showNewImagesCheckBox_)
                  .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.UNRELATED))
               .addGroup(layout.createSequentialGroup()
                  .addGroup(layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
                     .addGroup(layout.createSequentialGroup()
                        .addComponent(showInFolderButton_)
                        .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
                        .addComponent(abortButton_)
                        .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
                        .addComponent(pauseButton_)
                        .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
                        .addComponent(acquireAtCurrentButton_, javax.swing.GroupLayout.PREFERRED_SIZE, 105, javax.swing.GroupLayout.PREFERRED_SIZE))
                     .addGroup(layout.createSequentialGroup()
                        .addContainerGap()
                        .addGroup(layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
                           .addComponent(zPosLabel_)
                           .addGroup(layout.createSequentialGroup()
                              .addComponent(fpsLabel_)
                              .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
                              .addComponent(animationFPSSpinner_, javax.swing.GroupLayout.PREFERRED_SIZE, 45, javax.swing.GroupLayout.PREFERRED_SIZE))
                           .addComponent(elapsedTimeLabel_))))
                  .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED, javax.swing.GroupLayout.DEFAULT_SIZE, Short.MAX_VALUE)))
            .addComponent(tabbedPane_)
            .addContainerGap())
      );
      layout.setVerticalGroup(
         layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
         .addGroup(layout.createSequentialGroup()
            .addContainerGap(javax.swing.GroupLayout.DEFAULT_SIZE, Short.MAX_VALUE)
            .addGroup(layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
               .addComponent(tabbedPane_, javax.swing.GroupLayout.PREFERRED_SIZE, 187, javax.swing.GroupLayout.PREFERRED_SIZE)
               .addGroup(layout.createSequentialGroup()
                  .addGroup(layout.createParallelGroup(javax.swing.GroupLayout.Alignment.LEADING)
                     .addGroup(layout.createSequentialGroup()
                        .addGroup(layout.createParallelGroup(javax.swing.GroupLayout.Alignment.BASELINE)
                           .addComponent(showInFolderButton_)
                           .addComponent(abortButton_)
                           .addComponent(pauseButton_))
                        .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
                        .addComponent(zPosLabel_))
                     .addComponent(acquireAtCurrentButton_))
                  .addGap(2, 2, 2)
                  .addComponent(elapsedTimeLabel_, javax.swing.GroupLayout.PREFERRED_SIZE, 27, javax.swing.GroupLayout.PREFERRED_SIZE)
                  .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
                  .addGroup(layout.createParallelGroup(javax.swing.GroupLayout.Alignment.BASELINE)
                     .addComponent(fpsLabel_)
                     .addComponent(animationFPSSpinner_, javax.swing.GroupLayout.PREFERRED_SIZE, javax.swing.GroupLayout.DEFAULT_SIZE, javax.swing.GroupLayout.PREFERRED_SIZE))
                  .addPreferredGap(javax.swing.LayoutStyle.ComponentPlacement.RELATED)
                  .addComponent(showNewImagesCheckBox_))))
      );

      tabbedPane_.getAccessibleContext().setAccessibleName("Status");
   }// </editor-fold>//GEN-END:initComponents

   private void newSurfaceButton_ActionPerformed(java.awt.event.ActionEvent evt) {//GEN-FIRST:event_newSurfaceButton_ActionPerformed
      SurfaceInterpolator s = ((DisplayWindowSurfaceGridTableModel) surfaceGridTable_.getModel()).addNewSurface();
      selectedSurfaceGridIndex_ = SurfaceGridManager.getInstance().getIndex(s);
   }//GEN-LAST:event_newSurfaceButton_ActionPerformed

   private void showInterpCheckBox_ActionPerformed(java.awt.event.ActionEvent evt) {//GEN-FIRST:event_showInterpCheckBox_ActionPerformed
      display_.setSurfaceDisplaySettings(showInterpCheckBox_.isSelected(), showStagePositionsCheckBox_.isSelected());
      display_.drawOverlay();
   }//GEN-LAST:event_showInterpCheckBox_ActionPerformed

   private void showStagePositionsCheckBox_ActionPerformed(java.awt.event.ActionEvent evt) {//GEN-FIRST:event_showStagePositionsCheckBox_ActionPerformed
      display_.setSurfaceDisplaySettings(showInterpCheckBox_.isSelected(), showStagePositionsCheckBox_.isSelected());
      display_.drawOverlay();
   }//GEN-LAST:event_showStagePositionsCheckBox_ActionPerformed

   private void showNewImagesCheckBox_ActionPerformed(java.awt.event.ActionEvent evt) {//GEN-FIRST:event_showNewImagesCheckBox_ActionPerformed
      if (showNewImagesCheckBox_.isSelected()) {
         display_.unlockAllScroller();
      } else {
         display_.superlockAllScrollers();
      }
   }//GEN-LAST:event_showNewImagesCheckBox_ActionPerformed

   private void tabbedPane_StateChanged(javax.swing.event.ChangeEvent evt) {//GEN-FIRST:event_tabbedPane_StateChanged
      if (tabbedPane_.getSelectedIndex() == 0) { // grid           
         display_.setMode(DisplayPlus.SURFACE_AND_GRID);
         //show tooltip
         showInstructionLabel(((JPanel) tabbedPane_.getComponentAt(0)).getToolTipText());
      } else if (tabbedPane_.getSelectedIndex() == 1) { //explore
         display_.setMode(DisplayPlus.EXPLORE);
         showInstructionLabel(((JPanel) tabbedPane_.getComponentAt(1)).getToolTipText());
      }
   }//GEN-LAST:event_tabbedPane_StateChanged

   private void gridRowsSpinner_StateChanged(javax.swing.event.ChangeEvent evt) {//GEN-FIRST:event_gridRowsSpinner_StateChanged
      if (getCurrentSurfaceOrGrid() != null && getCurrentSurfaceOrGrid() instanceof MultiPosGrid) {
         ((MultiPosGrid) getCurrentSurfaceOrGrid()).updateParams((Integer) gridRowsSpinner_.getValue(), (Integer) gridColsSpinner_.getValue());
      }
   }//GEN-LAST:event_gridRowsSpinner_StateChanged

   private void newGridButton_ActionPerformed(java.awt.event.ActionEvent evt) {//GEN-FIRST:event_newGridButton_ActionPerformed
      MultiPosGrid r = ((DisplayWindowSurfaceGridTableModel) surfaceGridTable_.getModel()).newGrid(
              (Integer) gridRowsSpinner_.getValue(), (Integer) gridColsSpinner_.getValue(), display_.getCurrentDisplayedCoordinate());
      selectedSurfaceGridIndex_ = SurfaceGridManager.getInstance().getIndex(r);
   }//GEN-LAST:event_newGridButton_ActionPerformed

   private void showInFolderButton_ActionPerformed(java.awt.event.ActionEvent evt) {//GEN-FIRST:event_showInFolderButton_ActionPerformed
      display_.showFolder();
   }//GEN-LAST:event_showInFolderButton_ActionPerformed

   private void animationFPSSpinner_StateChanged(javax.swing.event.ChangeEvent evt) {//GEN-FIRST:event_animationFPSSpinner_StateChanged
      display_.setAnimateFPS(((Number) animationFPSSpinner_.getValue()).doubleValue());
   }//GEN-LAST:event_animationFPSSpinner_StateChanged

    private void pauseButton_ActionPerformed(java.awt.event.ActionEvent evt) {//GEN-FIRST:event_pauseButton_ActionPerformed
       acq_.togglePaused();
       pauseButton_.setIcon(new javax.swing.ImageIcon(getClass().getResource(
               acq_.isPaused() ? "main/resources/org/micromanager/play.png" : "main/resources/org/micromanager/pause.png")));
       repaint();
    }//GEN-LAST:event_pauseButton_ActionPerformed

    private void abortButton_ActionPerformed(java.awt.event.ActionEvent evt) {//GEN-FIRST:event_abortButton_ActionPerformed
       acq_.abort();
    }//GEN-LAST:event_abortButton_ActionPerformed

   private void gridColsSpinner_StateChanged(javax.swing.event.ChangeEvent evt) {//GEN-FIRST:event_gridColsSpinner_StateChanged
      if (getCurrentSurfaceOrGrid() != null && getCurrentSurfaceOrGrid() instanceof MultiPosGrid) {
         ((MultiPosGrid) getCurrentSurfaceOrGrid()).updateParams((Integer) gridRowsSpinner_.getValue(), (Integer) gridColsSpinner_.getValue());
      }
   }//GEN-LAST:event_gridColsSpinner_StateChanged

    private void acquireAtCurrentButton_ActionPerformed(java.awt.event.ActionEvent evt) {//GEN-FIRST:event_acquireAtCurrentButton_ActionPerformed
       ((ExploreAcquisition) acq_).acquireTileAtCurrentLocation(((DisplayWindow) display_.getImagePlus().getWindow()).getSubImageControls());
    }//GEN-LAST:event_acquireAtCurrentButton_ActionPerformed

   // Variables declaration - do not modify//GEN-BEGIN:variables
   private javax.swing.JButton abortButton_;
   private javax.swing.JButton acquireAtCurrentButton_;
   private javax.swing.JPanel addSurfaceGridButtonPanel_;
   private javax.swing.JSpinner animationFPSSpinner_;
   private javax.swing.JTable channelsTable_;
   private javax.swing.JLabel elapsedTimeLabel_;
   private javax.swing.JPanel explorePanel_;
   private javax.swing.JLabel fpsLabel_;
   private javax.swing.JLabel gridColsLabel_;
   private javax.swing.JSpinner gridColsSpinner_;
   private javax.swing.JPanel gridControlPanel_;
   private javax.swing.JLabel gridRowsLabel_;
   private javax.swing.JSpinner gridRowsSpinner_;
   private javax.swing.JLabel jLabel1;
   private javax.swing.JLabel jLabel2;
   private javax.swing.JScrollPane jScrollPane1;
   private javax.swing.JScrollPane jScrollPane2;
   private javax.swing.JButton newGridButton_;
   private javax.swing.JButton newSurfaceButton_;
   private javax.swing.JButton pauseButton_;
   private javax.swing.JButton showInFolderButton_;
   private javax.swing.JCheckBox showInterpCheckBox_;
   private javax.swing.JCheckBox showNewImagesCheckBox_;
   private javax.swing.JCheckBox showStagePositionsCheckBox_;
   private javax.swing.JPanel surfaceControlPanel_;
   private javax.swing.JPanel surfaceGridPanel_;
   private javax.swing.JPanel surfaceGridSpecificControlsPanel_;
   private javax.swing.JTable surfaceGridTable_;
   private javax.swing.JTabbedPane tabbedPane_;
   private javax.swing.JLabel zPosLabel_;
   // End of variables declaration//GEN-END:variables
}
