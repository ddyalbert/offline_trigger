#include "TFile.h"
#include "TTree.h"
#include "TH1D.h"
#include "TCanvas.h"
#include "TGraph.h"
#include "TF1.h"
#include "TStyle.h"

#include <iostream>
#include <fstream>

void analysis()
{
    gStyle->SetOptFit(1111);
    // TString folderName = "/mnt/wsl/disk/bolometer/Data/RUN33/WTh_CS_WP_ustcBox_1121/";
    // TString folderName = "/mnt/wsl/disk/bolometer/Data/RUN37/Na22_WTh_heater_0420/";
    TString folderName = "/mnt/wsl/disk/bolometer/Data/RUN37/Na22_WTh_0419/";
    TFile *f = new TFile(folderName + "SignalFiltered_v0.0.root", "READ");
    TTree *tree = (TTree*)f->Get("tree");


    Double_t Amp_fil;
    Double_t Amp_raw;
    Double_t Baseline;
    Double_t pk_interval;
    Double_t Amp_shift;
    Double_t ratio_fit;
    Double_t DT;
    Double_t RT;
    Double_t chi2_fil;
    Double_t chi2_raw;

    uint8_t isValid;

    tree->SetBranchAddress("Amp_fil", &Amp_fil);
    tree->SetBranchAddress("Amp_raw", &Amp_raw);
    tree->SetBranchAddress("Baseline", &Baseline);
    tree->SetBranchAddress("pk_interval", &pk_interval);
    tree->SetBranchAddress("DT", &DT);
    tree->SetBranchAddress("RT", &RT);
    tree->SetBranchAddress("chi2_fil", &chi2_fil);
    tree->SetBranchAddress("chi2_raw", &chi2_raw);  

    tree->SetBranchAddress("isValid", &isValid);
    tree->SetBranchAddress("Amp_shift", &Amp_shift);
    tree->SetBranchAddress("ratio_fit", &ratio_fit);
    

    TH1D *hist_amp   = new TH1D("hist_amp","Hist;Amp(V)", 300, 0, 3);
    TH1D *hist_amp_s = new TH1D("hist_amp_s", "Hist;Amp(V)", 300, 0, 3);
    TH1D *hist_E = new TH1D("hist_E", "Hist;E(MeV)", 2000, 0, 5);
    TGraph *graph_stabilize = new TGraph();

    TGraph *graph_raw_fil = new TGraph();
    TGraph *graph_amp_RT = new TGraph();
    TGraph *graph_amp_DT = new TGraph();
    TGraph *graph_amp_chi2 = new TGraph();
    TGraph *graph_amp_raw_chi2 = new TGraph();

    TGraph *graph_RT_DT = new TGraph();

    // stabilize fit params
    std::ifstream inFile("../.temp/fit_params.txt");
    Bool_t isSaveParams = false;
    Double_t pp[2] = {1.0, 0.0};
    if (inFile.is_open())
    {
        isSaveParams = true;
        inFile >> pp[0] >> pp[1];
    }

    double cc = 0.03;
    int n = tree->GetEntries();
    int n_cut = 0;
    tree->GetEntry(0);
    double min_distance = 0;
    for (size_t i = 0; i < n; i++)
    {
        if (pk_interval < min_distance) {
            tree->GetEntry(i);
            continue;
        }
        tree->GetEntry(i);
        if (pk_interval < min_distance) continue;
        if (!isValid) continue;
        if (Amp_fil <= 0) continue; 

        if (DT < 6 || DT > 10) continue;
        if (RT < 2.5 || RT > 4) continue;
        // if (chi2_fil > 0.03) continue;
        // if (chi2_raw > 0.02) continue;
        

        Double_t amp = Amp_fil;
        // Double_t amp_s = amp;
        Double_t amp_s = 1.5 * amp/ (pp[0] + pp[1] * Baseline);
        
        hist_amp->Fill(amp);
        hist_amp_s->Fill(amp_s);

        graph_raw_fil->AddPoint(Amp_raw, Amp_fil);
        graph_amp_RT->AddPoint(amp_s, RT);
        graph_amp_DT->AddPoint(amp_s, DT);
        graph_amp_chi2->AddPoint(amp_s, chi2_fil);
        graph_amp_raw_chi2->AddPoint(amp_s, chi2_raw);

        n_cut++;

        Double_t E = 1.66 * amp_s - 0.046;
        if(E < 0) continue;

        hist_E->Fill(E);

        if(amp < 1.5 || amp > 1.6) continue;
        if(isSaveParams){
            if (amp < pp[0] + pp[1] * Baseline - cc) continue;
            if (amp > pp[0] + pp[1] * Baseline + cc) continue;
        }
        // if(Baseline < -2.1 || Baseline > -1.7) continue;
        graph_stabilize->AddPoint(Baseline, amp);
    }
    std::cout << "num of events after  cut = " << n_cut << std::endl;
    std::cout << "num of events before cut = " << n << std::endl;

    TCanvas *canvas_amp = new TCanvas("canvas_amp", "canvas_amp");
    hist_amp->Draw();
    canvas_amp->SetLogy();
    hist_amp->SetStats(2);

    TCanvas *canvas_stab = new TCanvas("canvas_stab", "canvas_stab");
    hist_amp_s->Draw();
    canvas_stab->SetLogy();
    hist_amp_s->SetStats(2);

    // TCanvas *canvas_raw_fil = new TCanvas("canvas_raw_fil", "canvas_raw_fil");
    // graph_raw_fil->SetTitle(";Amp raw (V);Amp fil (V)");
    // graph_raw_fil->Draw("AP+");


    // TCanvas *canvas_amp_DT = new TCanvas("canvas_amp_DT", "amp - DT");
    // graph_amp_DT->SetTitle(";Amp (V);DT (ms)");
    // graph_amp_DT->Draw("AP+");

    // TCanvas *canvas_amp_RT = new TCanvas("canvas_amp_RT", "amp - RT");
    // graph_amp_RT->SetTitle(";Amp (V);RT (ms)");
    // graph_amp_RT->Draw("AP+");

    // TCanvas *canvas_amp_chi2 = new TCanvas("canvas_amp_chi2", "amp - chi2");
    // graph_amp_chi2->SetTitle(";Amp (V);chi2");
    // graph_amp_chi2->Draw("AP+");

    // TCanvas *canvas_amp_raw_chi2 = new TCanvas("canvas_amp_raw_chi2", "amp - raw chi2");
    // graph_amp_raw_chi2->SetTitle(";Amp (V);raw chi2");
    // graph_amp_raw_chi2->Draw("AP+");


    TCanvas *canvas_E = new TCanvas("canvas_E", "canvas_E");
    hist_E->Draw();
    canvas_E->SetLogy();
    canvas_E->SetGrid();
    hist_E->SetStats(1);

    // TF1 *guss1 = new TF1("guss1", "[0] * TMath::Gaus(x, [1], [2]) + [3] + [4] * x", 1.25, 1.3);
    // guss1->SetParNames("Amplitude", "Mean", "Sigma");
    // guss1->SetParameters(1, 1.27, 0.01, 10, 0);
    // hist_E->Fit(guss1,"R+");

    TF1 *guss2 = new TF1("guss2", "[0] * TMath::Gaus(x, [1], [2]) + + [3] + [4] * x", 0.49, 0.515);
    guss2->SetParNames("Amplitude", "Mean", "Sigma");
    guss2->SetParameters(10, 0.501, 0.01, 100, 0);
    hist_E->Fit(guss2,"R+");


    // TCanvas *canvas_stablize = new TCanvas("canvas_stablize", "canvas_stablize");
    // graph_stabilize->SetTitle(";Baseline (V);Amp (V)");
    // graph_stabilize->SetMarkerStyle(20);
    // graph_stabilize->SetMarkerSize(0.2);
    // graph_stabilize->Draw("AP+");

    // TF1 *linefit = new TF1("linefit", "[0] + [1] * x", -2.4, -1.8);
    // graph_stabilize->Fit(linefit);

    // std::ofstream outFile("../.temp/fit_params.txt");
    // outFile << linefit->GetParameter(0) << std::endl;
    // outFile << linefit->GetParameter(1) << std::endl;
    // outFile.close();

}